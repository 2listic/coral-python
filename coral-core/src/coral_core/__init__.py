"""coral-core — the shared contract for the coral plugin system.

A plugin subclasses :class:`Plugin` and exposes its callables through
``get_functions()`` / ``get_classes()``. The contract is an ABC so the two
methods are *enforced* (a subclass that omits either cannot be instantiated),
not merely duck-typed. The entry-point name under which a plugin registers (see
the host's ``coral.plugins`` group) is the plugin's identity — the contract
carries no ``name``.

A function or method may also name its outputs with :func:`outputs`. Python
names every parameter but has no syntax for naming a return value, so an output
name cannot be read from the code: it has to be declared. The host reads it back
through :func:`output_names`, never through the attribute itself.

This package depends on nothing internal: plugins and the host both import it,
it imports neither.
"""

import inspect
from abc import ABC, abstractmethod
from typing import Callable

__all__ = ["Plugin", "output_names", "outputs"]

# The attribute `outputs` sets. Only `output_names` reads it, so its name stays in this module.
_OUTPUTS_ATTRIBUTE = "_coral_outputs"


class Plugin(ABC):
    """Contract a plugin subclasses to expose its callables to the host."""

    @abstractmethod
    def get_functions(self) -> dict[str, Callable]:
        """Return a mapping of node ``type`` -> callable for this plugin."""

    @abstractmethod
    def get_classes(self) -> dict[str, type]:
        """Return a mapping of class name -> class for this plugin."""


def outputs(*names: str) -> Callable[[Callable], Callable]:
    """Name a function's or method's outputs, in output-port order.

    The decorator only marks: it stores the names on the function and returns the very same
    object. Signature, annotations and calling behaviour are untouched, so nothing that introspects
    or calls the function can tell it was decorated::

        @outputs("velocity", "smoke", "pressure")
        def iterate(...) -> Tuple[Any, Any, Any]: ...

    The names are checked here as far as they can be without the function. Whether there is one
    name per output port depends on the return annotation, so the host checks that when it reads
    the function.

    Raises:
        TypeError: if a name is not a string. A bare ``@outputs``, without parentheses, lands here
            too: it passes the function itself as the first name.
        ValueError: if no name is given, a name is empty, or a name repeats — two outputs with the
            same label could not be told apart.
    """
    for name in names:
        if not isinstance(name, str):
            raise TypeError(
                f"@outputs takes the output names as strings, got {name!r}; "
                f'write @outputs("name", ...)'
            )
    if not names:
        raise ValueError("@outputs needs at least one output name")
    if "" in names:
        raise ValueError(f"@outputs: an output name cannot be empty, got {names!r}")
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise ValueError(f"@outputs: output names must be distinct, repeated: {repeated}")

    def mark(func: Callable) -> Callable:
        # A class is refused because a constructor's single output is the instance, which the
        # registry writes with no output argument and so no name; a staticmethod/classmethod object
        # or a builtin, because the host would never read a mark on it.
        if not inspect.isfunction(func):
            raise TypeError(
                f"@outputs applies to a function or method, not {func!r}; "
                f"a constructor's output cannot be named"
            )
        setattr(func, _OUTPUTS_ATTRIBUTE, names)
        return func

    return mark


def output_names(func: Callable) -> tuple[str, ...] | None:
    """The output names declared on ``func`` with :func:`outputs`, or ``None`` if it declares none."""
    return getattr(func, _OUTPUTS_ATTRIBUTE, None)
