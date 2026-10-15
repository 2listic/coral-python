"""The nodes this plugin declares on callables defined elsewhere, with no wrapper.

``math.atan2`` is a builtin and ``fractions.Fraction`` a standard-library class: neither can be
decorated where it is defined, so both are declared with the call form, and ``annotations=``
supplies the types their signatures lack. What is pinned here is the declaration; the arithmetic is
the standard library's.
"""

import math
from fractions import Fraction

from coral_plugin_math import plugin


class TestMathAtan2:
    """``math.atan2``: a builtin function, declared as it is."""

    def test_it_is_the_builtin_itself(self):
        """GIVEN the node type ``math.atan2``
        WHEN its declaration is read
        THEN its target is ``math.atan2`` itself, not a wrapper."""
        assert plugin.functions()["math.atan2"].target is math.atan2

    def test_its_ports_are_typed_by_the_declaration(self):
        """GIVEN ``math.atan2``, whose signature carries no types
        WHEN its declaration is read
        THEN ``annotations=`` types both parameters and the return as ``float``."""
        assert plugin.functions()["math.atan2"].annotations == {
            "y": float,
            "x": float,
            "return": float,
        }


class TestFraction:
    """``fractions.Fraction``: a standard-library class, with one of its methods."""

    def test_the_class_itself_is_the_constructor(self):
        """GIVEN the node type ``Fraction``
        WHEN its declaration is read
        THEN its target is ``fractions.Fraction``, and its constructor's parameters are typed."""
        declaration = plugin.classes()["Fraction"]

        assert declaration.target is Fraction
        assert declaration.annotations == {"numerator": int, "denominator": int}

    def test_limit_denominator_is_its_only_method_node(self):
        """GIVEN ``Fraction``, which has many methods
        WHEN its method nodes are read
        THEN ``limit_denominator`` is the only one — methods are nodes only when declared — and it
        is the standard library's own function, with its ports typed."""
        methods = plugin.classes()["Fraction"].methods

        assert list(methods) == ["Fraction.limit_denominator"]
        method = methods["Fraction.limit_denominator"]
        assert method.attribute == "limit_denominator"
        assert method.declaration.target is Fraction.limit_denominator
        assert method.declaration.annotations == {"max_denominator": int, "return": Fraction}
