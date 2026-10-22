"""coral-plugin-string — the StringProcessor class and print_text.

Every node type is declared on :data:`plugin`, the ``coral_core.Plugin`` instance registered
under the ``coral.plugins`` entry-point group as ``string``.
"""

from coral_core import Plugin

__all__ = ["StringProcessor", "plugin"]

#: This plugin: the entry point's target, on which every node type below is declared.
plugin = Plugin()


@plugin.function
def print_text(value: str) -> None:
    """Print a string with a message.

    Named for what it prints. This plugin and ``coral-plugin-math`` both used to declare a
    ``print_result``, which the host resolved by silently letting the later plugin win; a duplicate
    node type is now a ``DuplicateNodeTypeError``, so each plugin names its own. The parameter is
    typed ``str`` rather than ``Any``, so the graph's edge-type check can judge an edge into it —
    but only when the source is typed too: an ``Any`` source still skips the check.
    """
    print(f"Print: {value}")


@plugin.cls
class StringProcessor:
    """A class for string operations"""

    def __init__(self, prefix: str = ""):
        """Initialize with optional prefix"""
        self.prefix = prefix

    @plugin.method(const=True)
    def concatenate(self, text: str) -> str:
        """Concatenate prefix with text"""
        result = self.prefix + text
        print(f"StringProcessor.concatenate('{text}') = '{result}'")
        return result

    @plugin.method(const=True)
    def repeat(self, text: str, times: int) -> str:
        """Repeat text n times"""
        result = text * times
        print(f"StringProcessor.repeat('{text}', {times}) = '{result}'")
        return result
