"""coral-plugin-string — the StringProcessor class and print_result.

Subclasses the coral-core ``Plugin`` contract; registered under the
``coral.plugins`` entry-point group as ``string``.
"""

from typing import Any, Dict

from coral_core import Plugin

__all__ = ["StringPlugin", "StringProcessor"]


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


class StringPlugin(Plugin):
    """String operations: the StringProcessor class and print_result."""

    def get_functions(self) -> Dict[str, Any]:
        """Return string operation function definitions"""
        return {
            "print_result": print_result,
        }

    def get_classes(self) -> Dict[str, Any]:
        """Return string operation class definitions"""
        return {
            "StringProcessor": StringProcessor,
        }
