"""coral-plugin-string — the StringProcessor class and print_text.

Subclasses the coral-core ``Plugin`` contract; registered under the
``coral.plugins`` entry-point group as ``string``.
"""

from typing import Any, Dict

from coral_core import Plugin

__all__ = ["StringPlugin", "StringProcessor"]


def print_text(value: str) -> None:
    """Print a string with a message.

    Named for what it prints. This plugin and ``coral-plugin-math`` both used to declare a
    ``print_result``, which the host resolved by silently letting the later plugin win; a duplicate
    node type is now a ``DuplicateNodeTypeError``, so each plugin names its own. The parameter is
    typed ``str`` rather than ``Any`` — an edge feeding it is then checkable by graph check 6.
    """
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
    """String operations: the StringProcessor class and print_text."""

    def get_functions(self) -> Dict[str, Any]:
        """Return string operation function definitions"""
        return {
            "print_text": print_text,
        }

    def get_classes(self) -> Dict[str, Any]:
        """Return string operation class definitions"""
        return {
            "StringProcessor": StringProcessor,
        }
