import math
from typing import Any, Dict, Tuple


# Print 

def print_result(value: Any) -> None:
    """Print the result with a message"""
    print(f"Print: {value}")


# Basic math operations

def add(a: float, b: float) -> float:
    """Add two numbers"""
    result = a + b
    print(f"add({a}, {b}) = {result}")
    return result


def multiply(a: float, b: float) -> float:
    """Multiply a by b"""
    result = a * b
    print(f"multiply({a}, {b}) = {result}")
    return result


# Wrapper functions for math module with proper type hints

def math_sqrt(x: float) -> float:
    """Calculate the square root of x"""
    result = math.sqrt(x)
    print(f"math.sqrt({x}) = {result}")
    return result


def math_sin(x: float) -> float:
    """Calculate the sine of x (in radians)"""
    result = math.sin(x)
    print(f"math.sin({x}) = {result}")
    return result


def math_cos(x: float) -> float:
    """Calculate the cosine of x (in radians)"""
    result = math.cos(x)
    print(f"math.cos({x}) = {result}")
    return result


def math_pow(x: float, y: float) -> float:
    """Calculate x raised to the power y"""
    result = math.pow(x, y)
    print(f"math.pow({x}, {y}) = {result}")
    return result


def test_tuple_return(x: float, y: float) -> Tuple[float, float, float]:
    """Test function that returns a tuple of three values"""
    result1 = x + y
    result2 = x * y
    result3 = x - y
    print(f"test_tuple_return({x}, {y}) = ({result1}, {result2}, {result3})")
    return result1, result2, result3


class Calculator:
    """A simple calculator class"""
    def __init__(self, initial_value: float = 0.0):
        """Initialize calculator with an initial value"""
        self.value = initial_value

    def add_to_value(self, amount: float) -> float:
        """Add amount to stored value"""
        self.value += amount
        print(f"Calculator.add_to_value({amount}) = {self.value}")
        return self.value

    def multiply_value(self, factor: float) -> float:
        """Multiply stored value by factor"""
        self.value *= factor
        print(f"Calculator.multiply_value({factor}) = {self.value}")
        return self.value

    def get_value(self) -> float:
        """Get current value"""
        print(f"Calculator.get_value() = {self.value}")
        return self.value


def get_functions() -> Dict[str, Any]:
    """Return math function definitions"""
    return {
        "print_result": print_result,
        "add": add,
        "multiply": multiply,
        "math.sqrt": math_sqrt,
        "math.sin": math_sin,
        "math.cos": math_cos,
        "math.pow": math_pow,
        "test_tuple_return": test_tuple_return,
    }


def get_classes() -> Dict[str, Any]:
    """Return math class definitions"""
    return {
        "Calculator": Calculator,
    }
