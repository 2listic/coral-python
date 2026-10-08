"""``outputs`` / ``output_names`` — how a function or method names its outputs.

Python names every parameter but gives a return value no name, so an output's name has to be
declared. The decorator only marks the function; the host reads the mark back through
``output_names``. Whether the number of names matches the number of outputs depends on the return
annotation, so that is the host's check, not this package's.
"""

import pytest
from coral_core import output_names, outputs


def unmarked(x: float) -> float:
    """A function nobody decorated."""
    return x


class TestTheMark:
    """The decorator stores the names and changes nothing else."""

    def test_the_decorated_function_is_the_same_object(self):
        """GIVEN a function
        WHEN it is decorated with @outputs
        THEN the decorator returns that very function, not a wrapper."""

        def pair(x: float) -> float:
            return x

        assert outputs("first")(pair) is pair

    def test_the_names_read_back_in_order(self):
        """GIVEN a function decorated with three names
        WHEN its output names are read
        THEN they come back as declared, in order."""

        @outputs("sum", "product", "difference")
        def triple(x: float, y: float):
            return x + y, x * y, x - y

        assert output_names(triple) == ("sum", "product", "difference")

    def test_an_unmarked_function_has_no_names(self):
        """GIVEN a function never decorated
        WHEN its output names are read
        THEN the answer is None, not an empty tuple."""
        assert output_names(unmarked) is None

    def test_a_method_in_a_class_body_is_marked(self):
        """GIVEN a method decorated inside its class body
        WHEN its output names are read through the class
        THEN the mark is there — a method is a plain function until it is bound."""

        class Counter:
            @outputs("count")
            def bump(self) -> int:
                return 1

        assert output_names(Counter.bump) == ("count",)


class TestTheNamesAreRefused:
    """What the decorator can judge without the function, it refuses at once — at import."""

    def test_a_bare_decorator_is_refused(self):
        """GIVEN @outputs written without parentheses
        WHEN it is applied
        THEN TypeError: the function itself arrived as a name, and is not a string."""
        with pytest.raises(TypeError, match="as strings"):

            @outputs
            def forgot(x: float) -> float:
                return x

    def test_a_non_string_name_is_refused(self):
        """GIVEN a name that is not a string
        WHEN the decorator is created
        THEN TypeError."""
        with pytest.raises(TypeError, match="as strings"):
            outputs("first", 2)

    def test_no_names_are_refused(self):
        """GIVEN @outputs() with no names
        WHEN the decorator is created
        THEN ValueError: a mark that names nothing is a mistake, not a choice."""
        with pytest.raises(ValueError, match="at least one"):
            outputs()

    def test_an_empty_name_is_refused(self):
        """GIVEN an empty string among the names
        WHEN the decorator is created
        THEN ValueError: "" is what an undeclared output already gets."""
        with pytest.raises(ValueError, match="cannot be empty"):
            outputs("first", "")

    def test_a_repeated_name_is_refused(self):
        """GIVEN the same name twice
        WHEN the decorator is created
        THEN ValueError naming it: two outputs with one label cannot be told apart."""
        with pytest.raises(ValueError, match="'first'"):
            outputs("first", "second", "first")


class TestOnlyFunctionsAreMarked:
    """The host reads the mark from plain functions only, so nothing else may carry one."""

    def test_a_class_is_refused(self):
        """GIVEN a class
        WHEN it is decorated
        THEN TypeError: a constructor's output is the instance, which carries no name."""
        with pytest.raises(TypeError, match="constructor"):

            @outputs("widget")
            class Widget:
                pass

    def test_a_staticmethod_object_is_refused(self):
        """GIVEN a staticmethod object, i.e. @outputs written above @staticmethod
        WHEN it is decorated
        THEN TypeError: the object is not a function, so the host would never see the mark."""
        with pytest.raises(TypeError, match="function or method"):
            outputs("value")(staticmethod(unmarked))

    def test_a_builtin_is_refused(self):
        """GIVEN a builtin function
        WHEN it is decorated
        THEN TypeError, rather than an AttributeError from setting the mark."""
        with pytest.raises(TypeError, match="function or method"):
            outputs("length")(len)
