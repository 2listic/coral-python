"""The ``Calculator`` class, used directly.

Worth knowing before reading: ``Calculator`` is **stateful** — every method mutates ``self.value`` and
returns it. That is unlike the host's builtin collection nodes, which are pure by design because a
node's result may be read by several downstream nodes in an order the topological sort chooses. A
stateful class node is not wrong, but its behaviour depends on *how many times* its methods run, so
these tests pin the mutation explicitly rather than only the returned value.
"""

import pytest
from coral_plugin_math import Calculator


class TestConstruction:
    """What a constructor node produces."""

    def test_it_holds_the_initial_value(self):
        """GIVEN an initial value
        WHEN a Calculator is constructed
        THEN it stores that value."""
        assert Calculator(10.0).value == 10.0

    def test_the_default_is_zero_but_unreachable_from_a_graph(self):
        """GIVEN no argument
        WHEN a Calculator is constructed
        THEN the value is 0.0.

        Reachable only from Python: graph check 4 requires every input port to be wired, so the
        default is dead from the graph side. It is asserted here because this is the only place it can
        be — and because deleting it would change this class's Python API."""
        assert Calculator().value == 0.0


class TestMethods:
    """Each method mutates the stored value and returns the new one."""

    def test_add_to_value_accumulates(self):
        """GIVEN a Calculator holding 10
        WHEN 5 is added
        THEN it returns 15 and now holds 15."""
        calculator = Calculator(10.0)

        assert calculator.add_to_value(5.0) == 15.0
        assert calculator.value == 15.0

    def test_multiply_value_scales(self):
        """GIVEN a Calculator holding 4
        WHEN it is multiplied by 2.5
        THEN it returns 10 and now holds 10."""
        calculator = Calculator(4.0)

        assert calculator.multiply_value(2.5) == 10.0
        assert calculator.value == 10.0

    def test_get_value_reads_without_changing(self):
        """GIVEN a Calculator holding a value
        WHEN get_value is called twice
        THEN both calls return that value and it is unchanged."""
        calculator = Calculator(7.0)

        assert calculator.get_value() == 7.0
        assert calculator.get_value() == 7.0
        assert calculator.value == 7.0

    def test_calls_compose_in_order(self):
        """GIVEN a Calculator holding 2
        WHEN it is added to and then multiplied
        THEN the result reflects both, in the order the calls happened: (2 + 3) * 4."""
        calculator = Calculator(2.0)

        calculator.add_to_value(3.0)

        assert calculator.multiply_value(4.0) == 20.0

    def test_repeating_a_call_repeats_the_mutation(self):
        """GIVEN a Calculator holding 1
        WHEN add_to_value(1) is called twice
        THEN it holds 3 — the state carries between calls.

        Spelled out because it is the property that makes this class node order-sensitive in a way a
        pure node is not."""
        calculator = Calculator(1.0)
        calculator.add_to_value(1.0)
        calculator.add_to_value(1.0)

        assert calculator.value == 3.0

    @pytest.mark.parametrize("amount", [0.0, -5.0, 2.5])
    def test_add_to_value_handles_any_amount(self, amount):
        """GIVEN any amount, including zero and negative
        WHEN it is added
        THEN the stored value moves by exactly that amount."""
        calculator = Calculator(10.0)

        assert calculator.add_to_value(amount) == 10.0 + amount


class TestPrintedOutput:
    """Each method prints under the node type a graph names it by."""

    def test_add_to_value_prints_the_new_value(self, capsys):
        """GIVEN a Calculator
        WHEN add_to_value is called
        THEN it prints `Calculator.add_to_value(...)` with the resulting value."""
        Calculator(10.0).add_to_value(5.0)

        assert "Calculator.add_to_value(5.0) = 15.0" in capsys.readouterr().out

    def test_multiply_value_prints_the_new_value(self, capsys):
        """GIVEN a Calculator
        WHEN multiply_value is called
        THEN it prints `Calculator.multiply_value(...)` with the resulting value."""
        Calculator(4.0).multiply_value(2.5)

        assert "Calculator.multiply_value(2.5) = 10.0" in capsys.readouterr().out

    def test_get_value_prints_what_it_read(self, capsys):
        """GIVEN a Calculator
        WHEN get_value is called
        THEN it prints the value it returned."""
        Calculator(7.0).get_value()

        assert "Calculator.get_value() = 7.0" in capsys.readouterr().out
