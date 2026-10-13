"""coral-plugin-math — mathematical operations and the Calculator class.

Every node type is declared on :data:`plugin`, the ``coral_core.Plugin`` instance registered
under the ``coral.plugins`` entry-point group as ``math`` (see pyproject.toml).

Three of them are callables defined elsewhere — ``math.atan2``, ``fractions.Fraction`` and its
``limit_denominator`` — declared as they are, with no wrapper: the living example of the call form.
"""

import math
from fractions import Fraction
from typing import Tuple

from coral_core import Plugin

__all__ = ["Calculator", "plugin"]

#: This plugin: the entry point's target, on which every node type below is declared.
plugin = Plugin()


# Print


@plugin.function
def print_number(value: float) -> None:
    """Print a number with a message.

    Named for what it prints. This plugin and ``coral-plugin-string`` both used to declare a
    ``print_result``, which the host resolved by silently letting the later plugin win; a duplicate
    node type is now a ``DuplicateNodeTypeError``, so each plugin names its own. The parameter is
    typed ``float`` rather than ``Any``, so the graph's edge-type check can judge an edge into it —
    but only when the source is typed too: an ``Any`` source still skips, and ``bool`` passes as a
    widening.
    """
    print(f"Print: {value}")


# Basic math operations


@plugin.function
def add(a: float, b: float) -> float:
    """Add two numbers"""
    result = a + b
    print(f"add({a}, {b}) = {result}")
    return result


@plugin.function
def multiply(a: float, b: float) -> float:
    """Multiply a by b"""
    result = a * b
    print(f"multiply({a}, {b}) = {result}")
    return result


# Wrapper functions for math module with proper type hints


@plugin.function(name="math.sqrt")
def math_sqrt(x: float) -> float:
    """Calculate the square root of x"""
    result = math.sqrt(x)
    print(f"math.sqrt({x}) = {result}")
    return result


@plugin.function(name="math.sin")
def math_sin(x: float) -> float:
    """Calculate the sine of x (in radians)"""
    result = math.sin(x)
    print(f"math.sin({x}) = {result}")
    return result


@plugin.function(name="math.cos")
def math_cos(x: float) -> float:
    """Calculate the cosine of x (in radians)"""
    result = math.cos(x)
    print(f"math.cos({x}) = {result}")
    return result


@plugin.function(name="math.pow")
def math_pow(x: float, y: float) -> float:
    """Calculate x raised to the power y"""
    result = math.pow(x, y)
    print(f"math.pow({x}, {y}) = {result}")
    return result


@plugin.function(name="test_tuple_return", outputs=("sum", "product", "difference"))
def tuple_return(x: float, y: float) -> Tuple[float, float, float]:
    """Test function that returns a tuple of three values.

    The **node type** is ``test_tuple_return`` (see its declaration above) and the printed line
    names it, because that is the name a graph author wired. The Python symbol deliberately differs:
    a symbol starting with ``test_`` is collected as a test by pytest's ``python_functions`` the
    moment a test module imports it, and would then be called with no arguments. Renaming the node
    type would be a platform-facing change; renaming the symbol is not.
    """
    result1 = x + y
    result2 = x * y
    result3 = x - y
    print(f"test_tuple_return({x}, {y}) = ({result1}, {result2}, {result3})")
    return result1, result2, result3


@plugin.cls
class Calculator:
    """A simple calculator class"""

    def __init__(self, initial_value: float = 0.0):
        """Initialize calculator with an initial value"""
        self.value = initial_value

    @plugin.method
    def add_to_value(self, amount: float) -> float:
        """Add amount to stored value"""
        self.value += amount
        print(f"Calculator.add_to_value({amount}) = {self.value}")
        return self.value

    @plugin.method
    def multiply_value(self, factor: float) -> float:
        """Multiply stored value by factor"""
        self.value *= factor
        print(f"Calculator.multiply_value({factor}) = {self.value}")
        return self.value

    @plugin.method
    def get_value(self) -> float:
        """Get current value"""
        print(f"Calculator.get_value() = {self.value}")
        return self.value


# Callables defined elsewhere, declared as they are. Neither the builtin nor the standard-library
# class can be decorated where it is defined, and their signatures carry no types, so
# `annotations=` supplies them.

plugin.function(
    math.atan2, name="math.atan2", annotations={"y": float, "x": float, "return": float}
)
plugin.cls(Fraction, annotations={"numerator": int, "denominator": int})
plugin.method(Fraction.limit_denominator, annotations={"max_denominator": int, "return": Fraction})
