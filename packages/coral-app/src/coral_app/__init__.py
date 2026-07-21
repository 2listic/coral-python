"""coral-app — the host: discovers, loads, and holds plugins.

Discovery is via stdlib ``importlib.metadata`` entry points (group
``coral.plugins``) and is **lazy**: :func:`discover` lists installed plugin
names without importing any of them; :func:`load` imports and instantiates only
the requested one. The host never imports a plugin module directly — it finds
them at runtime through standard metadata.

``build_function_map`` / ``build_class_map`` keep the same signatures they had
in the old ``definitions`` package, but are now re-backed by discovery: each
selected plugin is loaded and its ``get_functions()`` / ``get_classes()`` merged
in selection order (later wins on key collisions, e.g. the ``print_result``
duplicate shared by math and string).
"""

from importlib.metadata import entry_points
from typing import Any, Dict, List, Optional

from coral_core import Plugin

from coral_app.primitives import PRIMITIVES_MAP

__all__ = [
    "PLUGIN_GROUP",
    "discover",
    "load",
    "load_all",
    "build_function_map",
    "build_class_map",
    "PRIMITIVES_MAP",
]

#: The entry-point group plugins declare themselves under. Public API; stable.
PLUGIN_GROUP = "coral.plugins"


def discover() -> List[str]:
    """Return the names of all installed plugins, without importing any."""
    return sorted(ep.name for ep in entry_points(group=PLUGIN_GROUP))


def load(name: str) -> Plugin:
    """Import, instantiate, and return the plugin registered under ``name``.

    Imports only the requested plugin. Raises ``LookupError`` if no plugin is
    registered under ``name`` (D4: fail-loud, no silent skip), and ``TypeError``
    if the entry point does not resolve to a ``coral_core.Plugin`` subclass.
    """
    matches = entry_points(group=PLUGIN_GROUP, name=name)
    if not matches:
        raise LookupError(
            f"no plugin registered under {name!r} in group {PLUGIN_GROUP!r}"
        )
    ep = next(iter(matches))
    plugin_cls = ep.load()
    if not (isinstance(plugin_cls, type) and issubclass(plugin_cls, Plugin)):
        raise TypeError(
            f"plugin {name!r} resolved to {plugin_cls!r}, "
            "which is not a coral_core.Plugin subclass"
        )
    return plugin_cls()


def load_all(names: List[str]) -> List[Plugin]:
    """Load several plugins by name, preserving the order given."""
    return [load(name) for name in names]


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

    Args:
        include: Plugin names to load. If ``None``, loads every discovered plugin.
        exclude: Plugin names to drop, applied after ``include``.

    Returns:
        Mapping of function name -> callable, merged in selection order.

    Raises:
        LookupError: if a selected name is not a discoverable plugin (D4).
    """
    function_map: Dict[str, Any] = {}
    for name in _selected(include, exclude):
        function_map.update(load(name).get_functions())
    return function_map


def build_class_map(
    include: Optional[List[str]] = None, exclude: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Build the class map by merging the selected plugins' ``get_classes()``.

    Args:
        include: Plugin names to load. If ``None``, loads every discovered plugin.
        exclude: Plugin names to drop, applied after ``include``.

    Returns:
        Mapping of class name -> class, merged in selection order.

    Raises:
        LookupError: if a selected name is not a discoverable plugin (D4).
    """
    class_map: Dict[str, Any] = {}
    for name in _selected(include, exclude):
        class_map.update(load(name).get_classes())
    return class_map
