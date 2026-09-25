"""This plugin's functions, called directly.

No host, no graph, no registry: just the callables this plugin declares. Their *values* are this
package's business and nobody else's — how a function node is described and executed is the host's,
and is tested there on a designed specimen.

Every function here prints as well as returning, and the printed line is asserted wherever it is
part of what a user sees when a graph runs.
"""

import math

import pytest
from coral_plugin_math import (
    add,
    math_cos,
    math_pow,
    math_sin,
    math_sqrt,
    multiply,
    print_number,
    tuple_return,
)

# `tuple_return` is the callable behind the node type `test_tuple_return`. The two names differ so
# that importing it here does not hand pytest a `test_*` symbol to collect as a test — see the
# function's own docstring. The node type keeps its name; renaming one is platform-facing.


class TestArithmetic:
    """``add`` and ``multiply``: the two functions with no stdlib counterpart."""

    @pytest.mark.parametrize(
        "a, b, expected", [(2.0, 3.0, 5.0), (-1.0, 1.0, 0.0), (0.5, 0.25, 0.75), (0.0, 0.0, 0.0)]
    )
    def test_add_returns_the_sum(self, a, b, expected):
        """GIVEN two numbers
        WHEN add is called
        THEN it returns their sum."""
        assert add(a, b) == expected

    @pytest.mark.parametrize(
        "a, b, expected", [(4.0, 2.5, 10.0), (-2.0, 3.0, -6.0), (1.0, 0.0, 0.0)]
    )
    def test_multiply_returns_the_product(self, a, b, expected):
        """GIVEN two numbers
        WHEN multiply is called
        THEN it returns their product."""
        assert multiply(a, b) == expected

    def test_add_prints_what_it_computed(self, capsys):
        """GIVEN two numbers
        WHEN add is called
        THEN it prints the call and its result — this is the output a user sees from a graph run."""
        add(2.0, 3.0)

        assert "add(2.0, 3.0) = 5.0" in capsys.readouterr().out

    def test_multiply_prints_what_it_computed(self, capsys):
        """GIVEN two numbers
        WHEN multiply is called
        THEN it prints the call and its result."""
        multiply(4.0, 2.5)

        assert "multiply(4.0, 2.5) = 10.0" in capsys.readouterr().out


class TestStdlibWrappers:
    """The ``math.*`` wrappers exist to carry type hints the stdlib functions do not.

    Each is asserted against the stdlib function it wraps rather than a literal: the wrapper's job is
    to *delegate*, so restating the arithmetic here would test Python, and a copied constant would
    drift.
    """

    @pytest.mark.parametrize("x", [0.0, 1.0, 2.0, 16.0, 0.25])
    def test_sqrt_delegates(self, x):
        """GIVEN a non-negative number
        WHEN math_sqrt is called
        THEN it returns exactly math.sqrt(x)."""
        assert math_sqrt(x) == math.sqrt(x)

    @pytest.mark.parametrize("x", [0.0, 1.0, math.pi / 2, math.pi, -1.0])
    def test_sin_delegates(self, x):
        """GIVEN an angle in radians
        WHEN math_sin is called
        THEN it returns exactly math.sin(x)."""
        assert math_sin(x) == math.sin(x)

    @pytest.mark.parametrize("x", [0.0, 1.0, math.pi / 2, math.pi])
    def test_cos_delegates(self, x):
        """GIVEN an angle in radians
        WHEN math_cos is called
        THEN it returns exactly math.cos(x)."""
        assert math_cos(x) == math.cos(x)

    @pytest.mark.parametrize("x, y", [(2.0, 3.0), (9.0, 0.5), (5.0, 0.0), (2.0, -1.0)])
    def test_pow_delegates(self, x, y):
        """GIVEN a base and an exponent
        WHEN math_pow is called
        THEN it returns exactly math.pow(x, y) — and the argument order is not commutative."""
        assert math_pow(x, y) == math.pow(x, y)

    def test_pow_is_not_symmetric(self):
        """GIVEN two different numbers
        WHEN they are passed in each order
        THEN the results differ, which is why edge `target_input` ordering matters for this node."""
        assert math_pow(2.0, 3.0) == 8.0
        assert math_pow(3.0, 2.0) == 9.0

    def test_sqrt_of_a_negative_raises(self):
        """GIVEN a negative number
        WHEN math_sqrt is called
        THEN ValueError propagates: the wrapper adds annotations, not error handling.

        A graph wired to compute sqrt(-1) is a broken graph, and it fails where it happens rather
        than yielding a quiet NaN."""
        with pytest.raises(ValueError):
            math_sqrt(-1.0)

    def test_a_wrapper_prints_its_dotted_node_name(self, capsys):
        """GIVEN math_sqrt
        WHEN it is called
        THEN it prints under the node type the graph names it by, `math.sqrt`, not its Python name."""
        math_sqrt(16.0)

        assert "math.sqrt(16.0) = 4.0" in capsys.readouterr().out


class TestTupleReturn:
    """The one multi-output function this plugin declares."""

    def test_it_returns_three_values_in_order(self):
        """GIVEN two numbers
        WHEN the tuple-returning function is called
        THEN it returns (sum, product, difference) in that order.

        The order is the contract: a graph selects one of them by `source_output`, so swapping two
        would silently change every graph downstream."""
        assert tuple_return(5.0, 3.0) == (8.0, 15.0, 2.0)

    def test_the_difference_is_not_symmetric(self):
        """GIVEN the arguments in each order
        WHEN the third element is read
        THEN it changes sign — the third output is x - y, not |x - y|."""
        assert tuple_return(5.0, 3.0)[2] == 2.0
        assert tuple_return(3.0, 5.0)[2] == -2.0


class TestPrintNumber:
    """``print_number`` — this plugin's printer, renamed from the old shared ``print_result``."""

    def test_it_returns_nothing(self):
        """GIVEN a number
        WHEN print_number is called
        THEN it returns None: as a node it has no outputs, so no edge may leave it."""
        assert print_number(1.5) is None

    def test_it_prints_the_value(self, capsys):
        """GIVEN a number
        WHEN print_number is called
        THEN the value appears in stdout behind the `Print:` prefix."""
        print_number(2.5)

        assert "Print: 2.5" in capsys.readouterr().out
