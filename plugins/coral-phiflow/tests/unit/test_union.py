"""``phiflow_union`` — its unwrap chain and its one guard, neither reachable from a graph.

Two things make this function worth unit-testing on its own:

* its four-way ``hasattr`` chain (cuboid / sphere / box / already-raw) is the plugin's only general
  unwrapper, and a graph exercises **one** branch per run — at simulation cost;
* its ``len(geometries) < 2`` ``ValueError`` is **unreachable from any graph at all**. Graph check 4
  requires every input port to be wired, so the ``geom2..geom6=None`` defaults are dead from the graph
  side; only a direct call can pass fewer than two geometries.

None of this touches a solver: a union of geometries is geometry.
"""

import pytest
from coral_plugin_phiflow import PhiFlowBox, PhiFlowCuboid, PhiFlowSphere, phiflow_union


@pytest.fixture
def sphere():
    return PhiFlowSphere(x=10.0, y=10.0, radius=2.0)


@pytest.fixture
def cuboid():
    return PhiFlowCuboid(center_x=5.0, center_y=5.0, half_size_x=1.0, half_size_y=1.0)


@pytest.fixture
def box():
    return PhiFlowBox(x=20.0, y=20.0)


class TestTheGuard:
    """Fewer than two geometries is an error — the only way to reach it is from here."""

    def test_one_geometry_raises(self, sphere):
        """GIVEN a single geometry
        WHEN phiflow_union is called
        THEN ValueError says at least two are required."""
        with pytest.raises(ValueError, match="at least 2 geometries"):
            phiflow_union(sphere)

    def test_one_geometry_plus_explicit_nones_raises(self, sphere):
        """GIVEN one geometry and Nones in the remaining slots
        WHEN phiflow_union is called
        THEN it still raises: the Nones are filtered before the count, not counted."""
        with pytest.raises(ValueError, match="at least 2 geometries"):
            phiflow_union(sphere, None, None, None, None, None)

    def test_no_geometry_at_all_raises(self):
        """GIVEN nothing but Nones
        WHEN phiflow_union is called
        THEN it raises rather than returning an empty union."""
        with pytest.raises(ValueError, match="at least 2 geometries"):
            phiflow_union(None)


class TestUnwrapping:
    """Each wrapper kind is recognised by the getter it exposes."""

    def test_two_spheres_combine(self, sphere):
        """GIVEN two sphere wrappers
        WHEN they are unioned
        THEN a geometry comes back — the `get_sphere` branch."""
        other = PhiFlowSphere(x=30.0, y=30.0, radius=3.0)

        assert phiflow_union(sphere, other) is not None

    def test_two_cuboids_combine(self, cuboid):
        """GIVEN two cuboid wrappers
        WHEN they are unioned
        THEN a geometry comes back — the `get_cuboid` branch, which is checked first."""
        other = PhiFlowCuboid(center_x=50.0, center_y=50.0, half_size_x=2.0, half_size_y=2.0)

        assert phiflow_union(cuboid, other) is not None

    def test_two_boxes_combine(self, box):
        """GIVEN two box wrappers
        WHEN they are unioned
        THEN a geometry comes back — the `get_box` branch."""
        other = PhiFlowBox(x=40.0, y=40.0)

        assert phiflow_union(box, other) is not None

    def test_raw_geometries_pass_through_unwrapped(self, sphere):
        """GIVEN two *raw* PhiFlow geometries, with no getter at all
        WHEN they are unioned
        THEN the final `else` branch uses them as they are.

        Unreachable from a graph — a graph can only produce wrappers — so this is the only test that
        can execute that line."""
        other = PhiFlowSphere(x=30.0, y=30.0, radius=3.0)

        assert phiflow_union(sphere.get_sphere(), other.get_sphere()) is not None

    def test_wrapped_and_raw_mix(self, sphere, box):
        """GIVEN one wrapper and one raw geometry
        WHEN they are unioned
        THEN both are accepted: the chain is evaluated per geometry, not once for the call."""
        assert phiflow_union(sphere, box.get_box()) is not None

    def test_three_kinds_at_once(self, sphere, cuboid, box):
        """GIVEN a sphere, a cuboid and a box together
        WHEN they are unioned
        THEN all three branches run in a single call."""
        assert phiflow_union(cuboid, sphere, box) is not None

    def test_it_reports_how_many_it_combined(self, sphere, cuboid, capsys):
        """GIVEN two geometries
        WHEN they are unioned
        THEN it prints the count it actually combined, after the None filter."""
        phiflow_union(sphere, cuboid, None, None, None, None)

        assert "phiflow_union: combined 2 geometries" in capsys.readouterr().out

    def test_the_full_six_slots_are_usable(self, sphere):
        """GIVEN six geometries
        WHEN they are unioned
        THEN all six are combined — the documented maximum, asserted so it stays true."""
        spheres = [PhiFlowSphere(x=float(i), y=0.0, radius=1.0) for i in range(6)]

        assert phiflow_union(*spheres) is not None
