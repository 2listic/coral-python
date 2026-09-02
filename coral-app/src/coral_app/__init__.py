"""coral-app — the host: discovers, loads, and holds plugins.

Discovery is via stdlib ``importlib.metadata`` entry points (group
``coral.plugins``) and is **lazy**: :func:`discover` lists installed plugin
names without importing any of them; :func:`load` imports and instantiates only
the requested one. The host never imports a plugin module directly — it finds
them at runtime through standard metadata.

``build_function_map`` / ``build_class_map`` keep the same signatures they had
in the old ``definitions`` package, but are now re-backed by discovery: each
selected plugin is loaded and its ``get_functions()`` / ``get_classes()`` merged
in selection order. **A node type may have exactly one owner**: two contributors
declaring the same name raise :class:`DuplicateNodeTypeError`. The two surfaces
are merged separately, so a name claimed by a function *and* a class is invisible
here; :func:`coral_app.nodeports.build_port_table` is where the maps meet and
raises the same error.

The host owns two node surfaces of its own, present under every plugin selection
and with no plugin installed at all: ``PRIMITIVES_MAP`` (the primitive node
types, in :mod:`coral_app.primitives`) and ``BUILTIN_FUNCTIONS`` (the collection
operations, in :mod:`coral_app.builtin_nodes`).
"""

from importlib.metadata import entry_points
from typing import Any, Dict, List, Optional

from coral_core import Plugin

from coral_app.builtin_nodes import BUILTIN_FUNCTIONS
from coral_app.errors import DuplicateNodeTypeError
from coral_app.primitives import COLLECTION_TYPES, PRIMITIVES_MAP, TYPE_NAMES

__all__ = [
    "PLUGIN_GROUP",
    "DuplicateNodeTypeError",
    "discover",
    "load",
    "build_function_map",
    "build_class_map",
    "PRIMITIVES_MAP",
    "COLLECTION_TYPES",
    "TYPE_NAMES",
    "BUILTIN_FUNCTIONS",
]

#: The entry-point group plugins declare themselves under. Public API; stable.
PLUGIN_GROUP = "coral.plugins"


def discover() -> List[str]:
    """Return the names of all installed plugins, without importing any."""
    return sorted(ep.name for ep in entry_points(group=PLUGIN_GROUP))


def load(name: str) -> Plugin:
    """Import, instantiate, and return the plugin registered under ``name``.

    Imports only the requested plugin. Raises ``LookupError`` if no plugin is
    registered under ``name`` — fail loud, never skip silently — and
    ``TypeError`` if the entry point does not resolve to a ``coral_core.Plugin``
    subclass.
    """
    matches = entry_points(group=PLUGIN_GROUP, name=name)
    if not matches:
        raise LookupError(f"no plugin registered under {name!r} in group {PLUGIN_GROUP!r}")
    ep = next(iter(matches))
    plugin_cls = ep.load()
    if not (isinstance(plugin_cls, type) and issubclass(plugin_cls, Plugin)):
        raise TypeError(
            f"plugin {name!r} resolved to {plugin_cls!r}, which is not a coral_core.Plugin subclass"
        )
    return plugin_cls()


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
) -> Dict[str, Any]:
    """Build the function map by merging the selected plugins' ``get_functions()``.

    **One node type, one owner.** A duplicate name — between two plugins, or between a plugin and
    one of the host's ``BUILTIN_FUNCTIONS`` — raises :class:`DuplicateNodeTypeError`. There is no
    winner to pick: a graph names only the node type, so a silently shadowed ``list_append`` (or a
    plugin's function displaced by another plugin's) would change what every graph on the platform
    computes while looking identical in the JSON. Refusing the selection puts the error where it can
    be fixed — in the plugin that chose the name.

    This replaces the former "later wins" merge, which was never a designed rule but the behaviour
    of ``dict.update()`` in this loop; the one real duplicate it resolved (``print_result``, declared
    by both math and string) is gone — each plugin now names its own (``print_number`` /
    ``print_text``).

    Args:
        include: Plugin names to load. If ``None``, loads every discovered plugin.
        exclude: Plugin names to drop, applied after ``include``.

    Returns:
        Mapping of function name -> callable: the selected plugins merged in selection order, then
        the builtins. The builtins land last, so they also come last in ``node_types.json``, which
        leaves every plugin-contributed entry at the position it already had.

    Raises:
        LookupError: if a selected name is not a discoverable plugin.
        DuplicateNodeTypeError: if two contributors declare the same function name.
    """
    function_map: Dict[str, Any] = {}
    owner: Dict[str, str] = {}  # node type -> the plugin that declared it

    for name in _selected(include, exclude):
        for node_type, func in load(name).get_functions().items():
            if node_type in owner:
                raise DuplicateNodeTypeError(
                    f"node type {node_type!r} is declared by both plugin {owner[node_type]!r} "
                    f"and plugin {name!r}"
                )
            owner[node_type] = name
            function_map[node_type] = func

    # The host's own nodes land last, so they keep their position in `node_types.json` — but a
    # plugin may not claim one of their names either.
    for node_type, func in BUILTIN_FUNCTIONS.items():
        if node_type in owner:
            raise DuplicateNodeTypeError(
                f"node type {node_type!r} is a host builtin and cannot be declared by "
                f"plugin {owner[node_type]!r}"
            )
        function_map[node_type] = func

    return function_map


def build_class_map(
    include: Optional[List[str]] = None, exclude: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Build the class map by merging the selected plugins' ``get_classes()``.

    Same rule as :func:`build_function_map`, for the same reason: a class name is a node type
    (a constructor, plus one ``Class.method`` per method), so two plugins declaring one is
    unresolvable from the graph. There are no builtin classes, so plugins are the only contributors.

    Args:
        include: Plugin names to load. If ``None``, loads every discovered plugin.
        exclude: Plugin names to drop, applied after ``include``.

    Returns:
        Mapping of class name -> class, merged in selection order.

    Raises:
        LookupError: if a selected name is not a discoverable plugin.
        DuplicateNodeTypeError: if two plugins declare the same class name.
    """
    class_map: Dict[str, Any] = {}
    owner: Dict[str, str] = {}  # class name -> the plugin that declared it

    for name in _selected(include, exclude):
        for class_name, cls in load(name).get_classes().items():
            if class_name in owner:
                raise DuplicateNodeTypeError(
                    f"class {class_name!r} is declared by both plugin {owner[class_name]!r} "
                    f"and plugin {name!r}"
                )
            owner[class_name] = name
            class_map[class_name] = cls

    return class_map
