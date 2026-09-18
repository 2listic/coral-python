"""coral-plugin-pypde — py-pde PDE-solver wrappers.

Subclasses the coral-core ``Plugin`` contract; registered under the
``coral.plugins`` entry-point group as ``pypde``.

py-pde is a hard dependency of this distribution, so its import is unconditional: a broken
install fails loud with ``ImportError`` instead of silently registering nothing.
"""

from typing import Any, Dict

from coral_core import Plugin

__all__ = ["PyPDEPlugin"]


class PyPDEPlugin(Plugin):
    """py-pde PDE-solver wrappers."""

    def get_functions(self) -> Dict[str, Any]:
        """Return py-pde function definitions — this plugin declares none."""
        return {}

    def get_classes(self) -> Dict[str, Any]:
        """Return py-pde class definitions"""
        return {}
