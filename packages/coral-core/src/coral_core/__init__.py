"""coral-core — the shared contract for the coral plugin system.

A plugin subclasses :class:`Plugin` and exposes its callables through
``get_functions()`` / ``get_classes()``. The contract is an ABC so the two
methods are *enforced* (a subclass that omits either cannot be instantiated),
not merely duck-typed. The entry-point name under which a plugin registers (see
the host's ``coral.plugins`` group) is the plugin's identity — the contract
carries no ``name``.

This package depends on nothing internal: plugins and the host both import it,
it imports neither.
"""

from abc import ABC, abstractmethod
from typing import Callable

__all__ = ["Plugin"]


class Plugin(ABC):
    """Contract a plugin subclasses to expose its callables to the host."""

    @abstractmethod
    def get_functions(self) -> dict[str, Callable]:
        """Return a mapping of node ``type`` -> callable for this plugin."""

    @abstractmethod
    def get_classes(self) -> dict[str, type]:
        """Return a mapping of class name -> class for this plugin."""
