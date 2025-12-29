from typing import Any, Dict
 

def print_result(value: Any) -> None:
    """Print the result with a message"""
    print(f"Print: {value}")


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


def get_functions() -> Dict[str, Any]:
    """Return string operation function definitions (none for this module)"""
    return {
        "print_result": print_result,
    }


def get_classes() -> Dict[str, Any]:
    """Return string operation class definitions"""
    return {
        "StringProcessor": StringProcessor,
    }
