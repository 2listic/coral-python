"""
Coral Definitions Package

This package provides modular function and class definitions for the Coral workflow system.
It organizes definitions by domain to facilitate selective loading and library independence.

Available modules:
- phiflow_defs: PhiFlow physics simulation wrappers
- primitives: Type mapping for primitive values
- math_ops: Mathematical operations and Calculator class
- string_ops: String processing utilities

Usage:
    from definitions import build_function_map, build_class_map, PRIMITIVES_MAP

    # Load all available definitions
    FUNCTION_MAP = build_function_map()
    CLASS_MAP = build_class_map()

    # Load specific modules only
    FUNCTION_MAP = build_function_map(include=['phiflow'])
    CLASS_MAP = build_class_map(include=['phiflow'])
"""

from typing import Dict, Any, List, Optional
from . import math_ops, string_ops, phiflow_defs, primitives

# Export PRIMITIVES_MAP for direct access
PRIMITIVES_MAP = primitives.PRIMITIVES_MAP


def build_function_map(include: Optional[List[str]] = None, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Build FUNCTION_MAP from specified modules.

    Args:
        include: List of module names to include. If None, includes all available modules.
                 Valid names: 'math', 'string', 'phiflow'
        exclude: List of module names to exclude. Applied after include filter.

    Returns:
        Dictionary mapping function names to callable functions

    Examples:
        # Load everything
        >>> build_function_map()

        # Load only PhiFlow
        >>> build_function_map(include=['phiflow'])

        # Load everything except string operations
        >>> build_function_map(exclude=['string'])
    """
    modules = {
        'math': math_ops,
        'string': string_ops,
        'phiflow': phiflow_defs,
    }

    # Determine which modules to load
    if include is None:
        include = list(modules.keys())

    if exclude is not None:
        include = [name for name in include if name not in exclude]

    # Build function map
    function_map = {}
    for name in include:
        if name in modules:
            module_functions = modules[name].get_functions()
            function_map.update(module_functions)
        else:
            print(f"Warning: Unknown module '{name}' in include list")

    return function_map


def build_class_map(include: Optional[List[str]] = None, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Build CLASS_MAP from specified modules.

    Args:
        include: List of module names to include. If None, includes all available modules.
                 Valid names: 'math', 'string', 'phiflow'
        exclude: List of module names to exclude. Applied after include filter.

    Returns:
        Dictionary mapping class names to Python classes

    Examples:
        # Load everything
        >>> build_class_map()

        # Load only PhiFlow classes
        >>> build_class_map(include=['phiflow'])

        # Load everything except math classes
        >>> build_class_map(exclude=['math'])
    """
    modules = {
        'math': math_ops,
        'string': string_ops,
        'phiflow': phiflow_defs,
    }

    # Determine which modules to load
    if include is None:
        include = list(modules.keys())

    if exclude is not None:
        include = [name for name in include if name not in exclude]

    # Build class map
    class_map = {}
    for name in include:
        if name in modules:
            module_classes = modules[name].get_classes()
            class_map.update(module_classes)
        else:
            print(f"Warning: Unknown module '{name}' in include list")

    return class_map


# For backward compatibility, provide default maps that include everything
FUNCTION_MAP = build_function_map()
CLASS_MAP = build_class_map()


__all__ = [
    'build_function_map',
    'build_class_map',
    'FUNCTION_MAP',
    'CLASS_MAP',
    'PRIMITIVES_MAP',
]
