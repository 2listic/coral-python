from typing import Any


# Define the functions that can be called by nodes
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


def print_result(value: Any) -> None:
    """Print the result with a message"""
    print(f"Print: {value}")


# Map function names to actual functions
FUNCTION_MAP = {
    "add": add,
    "multiply": multiply,
    "print_result": print_result
}


PRIMITIVES = ["int", "float", "str", "bool", "any"]
