"""coral-app — the host: discovers, loads, and holds plugins.

Discovery is via stdlib ``importlib.metadata`` entry points (group
``coral.plugins``) and is **lazy**: :func:`discover` lists installed plugin
names without importing any of them; :func:`load` imports only the requested
one. The host never imports a plugin module directly — it finds
them at runtime through standard metadata.

``build_function_map`` / ``build_class_map`` keep the same signatures they had
in the old ``definitions`` package, but are now re-backed by discovery: each
selected plugin is loaded and its declarations (``functions()`` / ``classes()``)
merged in selection order. **A node type may have exactly one owner**: two contributors
declaring the same name raise :class:`DuplicateNodeTypeError`. The two surfaces
are merged separately, so a name claimed by a function *and* a class is invisible
here; :func:`coral_app.nodeports.build_port_table` is where the maps meet and
raises the same error.

The host owns two node surfaces of its own, present under every plugin selection
and with no plugin installed at all: ``PRIMITIVES_MAP`` (the primitive node
types, in :mod:`coral_app.primitives`) and ``BUILTINS`` (the collection
operations, in :mod:`coral_app.builtin_nodes`).
"""

from importlib.metadata import entry_points
from typing import Dict, List, Optional

from coral_core import ClassDeclaration, Declaration, Plugin

from coral_app import legacy
from coral_app.builtin_nodes import BUILTINS
from coral_app.errors import DuplicateNodeTypeError
from coral_app.primitives import PRIMITIVES_MAP

__all__ = [
    "PLUGIN_GROUP",
    "DuplicateNodeTypeError",
    "discover",
    "load",
    "build_function_map",
    "build_class_map",
    "PRIMITIVES_MAP",
    "BUILTINS",
]

#: The entry-point group plugins declare themselves under. Public API; stable.
PLUGIN_GROUP = "coral.plugins"


def discover() -> List[str]:
    """Return the names of all installed plugins, without importing any."""
    return sorted(ep.name for ep in entry_points(group=PLUGIN_GROUP))


def load(name: str) -> Plugin:
    """Import and return the plugin registered under ``name``.

    Imports only the requested plugin. The entry point resolves to a ``coral_core.Plugin``
    instance, returned as is, or to a ``Plugin`` subclass written against the subclassing
    contract, which is instantiated. Raises ``LookupError`` if no plugin is registered under
    ``name`` — fail loud, never skip silently — and ``TypeError`` if the entry point resolves to
    anything else.
    """
    matches = entry_points(group=PLUGIN_GROUP, name=name)
    if not matches:
        raise LookupError(f"no plugin registered under {name!r} in group {PLUGIN_GROUP!r}")
    ep = next(iter(matches))
    target = ep.load()
    if isinstance(target, Plugin):
        return target
    if isinstance(target, type) and issubclass(target, Plugin):
        return target()
    raise TypeError(
        f"plugin {name!r} resolved to {target!r}, which is neither a coral_core.Plugin instance "
        f"nor a Plugin subclass"
    )


def _functions_of(plugin: Plugin) -> Dict[str, Declaration]:
    """A plugin's function declarations, whichever contract it is written against."""
    if legacy.is_legacy(plugin):
        return legacy.function_declarations(plugin.get_functions())
    return plugin.functions()


def _classes_of(plugin: Plugin) -> Dict[str, ClassDeclaration]:
    """A plugin's class declarations, whichever contract it is written against."""
    if legacy.is_legacy(plugin):
        return legacy.class_declarations(plugin.get_classes())
    return plugin.classes()


def _selected(include: Optional[List[str]], exclude: Optional[List[str]]) -> List[str]:
    """Resolve the include/exclude pair to an ordered list of plugin names.

    ``include=None`` means "all discovered" (sorted, deterministic). ``exclude``
    is applied afterwards, preserving order.
    """
    names = list(include) if include is not None else discover()
    if exclude is not None:
        names = [name for name in names if name not in exclude]
    return names


def build_function_map(
    include: Optional[List[str]] = None, exclude: Optional[List[str]] = None
) -> Dict[str, Declaration]:
    """Build the function map by merging the selected plugins' function declarations.

    **One node type, one owner.** A duplicate name — between two plugins, or between a plugin and
    one of the host's ``BUILTINS`` — raises :class:`DuplicateNodeTypeError`. There is no
    winner to pick: a graph names only the node type, so a silently shadowed ``list_append`` would
    change what every graph computes while the JSON looks identical. Refusing the selection puts the
    error in the plugin that chose the name.

    Args:
        include: Plugin names to load. If ``None``, loads every discovered plugin.
        exclude: Plugin names to drop, applied after ``include``.

    Returns:
        Mapping of function name -> :class:`coral_core.Declaration`: the selected plugins merged in
        selection order, then the builtins. The builtins land last, so they also come last in
        ``node_types.json``, which leaves every plugin-contributed entry at the position it already
        had.

    Raises:
        LookupError: if a selected name is not a discoverable plugin.
        DuplicateNodeTypeError: if two contributors declare the same function name.
    """
    function_map: Dict[str, Declaration] = {}
    owner: Dict[str, str] = {}  # node type -> the plugin that declared it

    for name in _selected(include, exclude):
        for node_type, declaration in _functions_of(load(name)).items():
            if node_type in owner:
                raise DuplicateNodeTypeError(
                    f"node type {node_type!r} is declared by both plugin {owner[node_type]!r} "
                    f"and plugin {name!r}"
                )
            owner[node_type] = name
            function_map[node_type] = declaration

    # The host's own nodes land last, so they keep their position in `node_types.json` — but a
    # plugin may not claim one of their names either.
    for node_type, declaration in BUILTINS.functions().items():
        if node_type in owner:
            raise DuplicateNodeTypeError(
                f"node type {node_type!r} is a host builtin and cannot be declared by "
                f"plugin {owner[node_type]!r}"
            )
        function_map[node_type] = declaration

    return function_map


def build_class_map(
    include: Optional[List[str]] = None, exclude: Optional[List[str]] = None
) -> Dict[str, ClassDeclaration]:
    """Build the class map by merging the selected plugins' class declarations.

    Same rule as :func:`build_function_map`, for the same reason: a class name is a node type
    (a constructor, plus one ``Class.method`` per method), so two plugins declaring one is
    unresolvable from the graph. There are no builtin classes, so plugins are the only contributors.

    Args:
        include: Plugin names to load. If ``None``, loads every discovered plugin.
        exclude: Plugin names to drop, applied after ``include``.

    Returns:
        Mapping of class name -> :class:`coral_core.ClassDeclaration`, merged in selection order.

    Raises:
        LookupError: if a selected name is not a discoverable plugin.
        DuplicateNodeTypeError: if two plugins declare the same class name.
    """
    class_map: Dict[str, ClassDeclaration] = {}
    owner: Dict[str, str] = {}  # class name -> the plugin that declared it

    for name in _selected(include, exclude):
        for class_name, declaration in _classes_of(load(name)).items():
            if class_name in owner:
                raise DuplicateNodeTypeError(
                    f"class {class_name!r} is declared by both plugin {owner[class_name]!r} "
                    f"and plugin {name!r}"
                )
            owner[class_name] = name
            class_map[class_name] = declaration

    return class_map
