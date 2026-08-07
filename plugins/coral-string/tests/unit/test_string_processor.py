"""This plugin's whole surface, called directly: ``StringProcessor`` and ``print_text``.

No host, no graph, no registry — just the callables. How a class becomes a constructor node and its
methods become ``Class.method`` nodes is the host's business, tested there against a designed
specimen.

Unlike math's ``Calculator``, ``StringProcessor`` is **stateless** after construction: the prefix is
set once and every method is a pure function of its arguments. That is worth pinning, because a node
whose result depends on how many times it has run behaves differently in a graph.
"""

import pytest
from coral_plugin_string import StringProcessor, print_text


class TestConstruction:
    """What a constructor node produces."""

    def test_it_holds_the_prefix(self):
        """GIVEN a prefix
        WHEN a StringProcessor is constructed
        THEN it stores that prefix."""
        assert StringProcessor("Hello, ").prefix == "Hello, "

    def test_the_default_prefix_is_empty_but_unreachable_from_a_graph(self):
        """GIVEN no argument
        WHEN a StringProcessor is constructed
        THEN the prefix is the empty string.

        Reachable only from Python: graph check 4 requires every input port to be wired, so the
        default is dead from the graph side. Asserted here because this is the only place it can be."""
        assert StringProcessor().prefix == ""


class TestConcatenate:
    """``concatenate`` prepends the stored prefix."""

    @pytest.mark.parametrize(
        "prefix, text, expected",
        [
            ("Hello, ", "world", "Hello, world"),
            ("", "world", "world"),
            ("a", "", "a"),
            ("", "", ""),
        ],
    )
    def test_it_prepends_the_prefix(self, prefix, text, expected):
        """GIVEN a prefix and a text
        WHEN concatenate is called
        THEN it returns prefix + text, in that order."""
        assert StringProcessor(prefix).concatenate(text) == expected

    def test_it_does_not_consume_the_prefix(self):
        """GIVEN one StringProcessor
        WHEN concatenate is called twice
        THEN both calls return the same thing.

        The instance is stateless after construction, so a method node's result does not depend on how
        many times it ran — unlike a mutating class node."""
        processor = StringProcessor("Hello, ")

        assert processor.concatenate("world") == "Hello, world"
        assert processor.concatenate("world") == "Hello, world"
        assert processor.prefix == "Hello, "

    def test_it_prints_what_it_produced(self, capsys):
        """GIVEN a StringProcessor
        WHEN concatenate is called
        THEN it prints the call and the resulting string, quoted."""
        StringProcessor("Hello, ").concatenate("world")

        assert "StringProcessor.concatenate('world') = 'Hello, world'" in capsys.readouterr().out


class TestRepeat:
    """``repeat`` multiplies the text, and ignores the prefix."""

    @pytest.mark.parametrize(
        "text, times, expected",
        [("ab", 3, "ababab"), ("x", 1, "x"), ("x", 0, ""), ("x", -1, "")],
    )
    def test_it_repeats_the_text(self, text, times, expected):
        """GIVEN a text and a count
        WHEN repeat is called
        THEN it returns the text repeated that many times — zero and negative both give ''.

        That is Python's `str * int`, not a guard: the wrapper adds annotations, not validation, so a
        graph asking for -1 copies gets the empty string rather than an error."""
        assert StringProcessor("ignored: ").repeat(text, times) == expected

    def test_it_ignores_the_prefix(self):
        """GIVEN a StringProcessor with a prefix
        WHEN repeat is called
        THEN the prefix does not appear: only concatenate uses it."""
        assert StringProcessor("Hello, ").repeat("ab", 2) == "abab"

    def test_swapping_the_arguments_is_not_caught_at_run_time(self):
        """GIVEN the text and the count passed in the wrong order
        WHEN repeat is called
        THEN it still returns a string, because `int * str` is valid Python.

        Worth knowing, and slightly uncomfortable: a graph with `target_input` 1 and 2 swapped on this
        node produces a plausible result instead of an error. Nothing *inside* this plugin can catch
        that — which is precisely what makes the annotations load-bearing. `repeat(text: str,
        times: int)` is fully annotated, so the swapped wiring is rejected by graph check 6 before
        execution: `str` into an `int` port is refused. This test records that the run-time behaviour
        is no defence, and `test_the_annotations_are_what_reject_a_swap` in the conformance module
        records that the annotations are."""
        assert StringProcessor("").repeat(3, "ab") == "ababab"

    def test_it_prints_what_it_produced(self, capsys):
        """GIVEN a StringProcessor
        WHEN repeat is called
        THEN it prints the call and the resulting string."""
        StringProcessor("").repeat("ab", 2)

        assert "StringProcessor.repeat('ab', 2) = 'abab'" in capsys.readouterr().out


class TestPrintText:
    """``print_text`` — this plugin's printer, renamed from the old shared ``print_result``."""

    def test_it_returns_nothing(self):
        """GIVEN a string
        WHEN print_text is called
        THEN it returns None: as a node it has no outputs, so no edge may leave it."""
        assert print_text("anything") is None

    def test_it_prints_the_value(self, capsys):
        """GIVEN a string
        WHEN print_text is called
        THEN the value appears in stdout behind the `Print:` prefix."""
        print_text("Hello, world")

        assert "Print: Hello, world" in capsys.readouterr().out
