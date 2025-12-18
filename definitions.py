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


class StringProcessor:
    """A class for string operations"""
    def __init__(self, prefix: str = ""):
        """Initialize with optional prefix"""
        self.prefix = prefix
    
    def concatenate(self, text: str) -> str:
        """Concatenate prefix with text"""
        result = self.prefix + text
        print(f"StringProcessor.concatenate('{text}') = '{result}'")
        return result
    
    def repeat(self, text: str, times: int) -> str:
        """Repeat text n times"""
        result = text * times
        print(f"StringProcessor.repeat('{text}', {times}) = '{result}'")
        return result


# Map class names to classes
CLASS_MAP = {
    "Calculator": Calculator,
    "StringProcessor": StringProcessor
}


# Map function names to actual functions
FUNCTION_MAP = {
    "add": add,
    "multiply": multiply,
    "print_result": print_result
}

# Map primitive type names to Python types
PRIMITIVES_MAP = {
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "any": Any,
    "none": type(None),
}
