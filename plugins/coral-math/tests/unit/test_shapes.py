"""The shape hierarchy, used directly.

``Square`` derives from ``Regular`` first and ``Rectangle`` second, and only ``Rectangle`` is a
``Shape``. These tests pin that Python sees a ``Square`` as all three, which is what the registry's
``bases`` then reports; whether a graph accepts it is the system suite's business.
"""

import math

import pytest
from coral_plugin_math import Rectangle, Regular, Shape, Square, rectangle_diagonal, shape_area


class TestRectangle:
    """A rectangle's own arithmetic."""

    def test_area_is_width_times_height(self):
        """GIVEN a 3 by 4 rectangle
        WHEN its area is asked
        THEN it is 12."""
        assert Rectangle(3.0, 4.0).area() == 12.0

    def test_diagonal_is_the_hypotenuse(self):
        """GIVEN a 3 by 4 rectangle
        WHEN its diagonal is asked
        THEN it is 5."""
        assert Rectangle(3.0, 4.0).diagonal() == 5.0


class TestSquare:
    """A square: a rectangle whose two sides are the one given."""

    def test_area_is_the_side_squared(self):
        """GIVEN a square of side 3
        WHEN its area is asked
        THEN it is 9."""
        assert Square(3.0).area() == 9.0

    def test_diagonal_is_the_rectangle_s(self):
        """GIVEN a square of side 3
        WHEN its diagonal is asked
        THEN it is that of a 3 by 3 rectangle."""
        assert Square(3.0).diagonal() == math.hypot(3.0, 3.0)

    @pytest.mark.parametrize("ancestor", [Regular, Rectangle, Shape])
    def test_it_is_an_instance_of_every_ancestor(self, ancestor):
        """GIVEN a square
        WHEN it is checked against each of its ancestors
        THEN it is an instance of each: the first parent, the second, and the second's base."""
        assert isinstance(Square(3.0), ancestor)


class TestShape:
    """The abstract root."""

    def test_it_cannot_be_instantiated(self):
        """GIVEN Shape, whose area is abstract
        WHEN it is instantiated
        THEN Python refuses it."""
        with pytest.raises(TypeError):
            Shape()


class TestFunctions:
    """The two functions are the methods, reachable as functions."""

    def test_shape_area_is_the_method_s(self):
        """GIVEN a square
        WHEN shape_area is called on it
        THEN it returns what its area method returns."""
        square = Square(3.0)
        assert shape_area(square) == square.area()

    def test_rectangle_diagonal_is_the_method_s(self):
        """GIVEN a square
        WHEN rectangle_diagonal is called on it
        THEN it returns what its diagonal method returns."""
        square = Square(3.0)
        assert rectangle_diagonal(square) == square.diagonal()
