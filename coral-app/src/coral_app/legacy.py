"""Declarations for plugins written against the subclassing contract.

Such a plugin subclasses :class:`coral_core.Plugin`, overrides ``get_functions()`` /
``get_classes()`` and names outputs with ``coral_core.outputs``. This module turns what it returns
into the declarations a decorated plugin hands over, reproducing how that contract was read: every
public pure-Python method of a class is a method node, named by its attribute, and its output names
are the ones ``@outputs`` stored on it.
"""

import inspect
from typing import Callable, Dict, List, Mapping

from coral_core import ClassDeclaration, Declaration, MethodDeclaration, Plugin, output_names

__all__ = ["class_declarations", "function_declarations", "is_legacy"]


def is_legacy(plugin: Plugin) -> bool:
    """Whether ``plugin`` answers through overridden ``get_functions()`` / ``get_classes()``.

    Decided by the override, not by what the entry point resolved to: a test can hand the host an
    instance of a subclassing plugin.
    """
    return type(plugin).get_functions is not Plugin.get_functions


def function_declarations(functions: Mapping[str, Callable]) -> Dict[str, Declaration]:
    """``{name: function}`` as declarations, output names read from ``@outputs``."""
    return {name: Declaration(func, outputs=output_names(func)) for name, func in functions.items()}


def class_declarations(classes: Mapping[str, type]) -> Dict[str, ClassDeclaration]:
    """``{key: class}`` as declarations: every public pure-Python method is a method node.

    Raises:
        ValueError: if a class's ``__init__`` is marked with ``@outputs``: a constructor's output
            is the instance, which carries no name.
    """
    declarations = {}
    for key, cls in classes.items():
        if output_names(cls.__init__) is not None:
            raise ValueError(
                f"Class {cls.__name__!r} marks __init__ with @outputs, but a constructor's output "
                f"cannot be named: it is the instance, which carries no name. Remove the decorator."
            )
        methods = {}
        for attribute in _public_method_names(cls):
            method = getattr(cls, attribute)
            methods[f"{key}.{attribute}"] = MethodDeclaration(
                attribute, Declaration(method, outputs=output_names(method))
            )
        declarations[key] = ClassDeclaration(cls, methods=methods)
    return declarations


def _public_method_names(cls: type) -> List[str]:
    """Names of the class's public, pure-Python instance methods, in ``dir()`` order.

    C extension methods are not ``inspect.isfunction``, so a C extension class yields none.
    """
    names = []
    for method_name in dir(cls):
        if method_name.startswith("_"):
            continue
        method = getattr(cls, method_name)
        if not callable(method) or not inspect.isfunction(method):
            continue
        names.append(method_name)
    return names
