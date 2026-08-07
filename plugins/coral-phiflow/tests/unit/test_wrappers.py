"""The wrapper classes, constructed directly — no solver, no simulation.

These had **no unit tests at all**: every line of them was covered only as a side effect of a fluid
simulation costing 6 to 33 seconds, which meant a broken constructor was found by a slow test and a
broken *branch* was often not found at all.

Constructing a geometry or a grid is milliseconds: `Box`, `Sphere`, `Cuboid` are geometry objects, and
a `StaggeredGrid` / `CenteredGrid` is an allocation. Nothing here calls ``fluid.make_incompressible``,
``iterate`` or ``plot``, which are what actually cost time — those stay behind the one ``slow`` example.
"""

import pytest
from coral_plugin_phiflow import (
    PhiFlowBox,
    PhiFlowCenteredGrid,
    PhiFlowCuboid,
    PhiFlowSphere,
    PhiFlowStaggeredGrid,
)


class TestGeometryWrappers:
    """``PhiFlowBox`` / ``PhiFlowSphere`` / ``PhiFlowCuboid``: a PhiFlow geometry behind a getter."""

    def test_a_box_holds_a_phiflow_box(self):
        """GIVEN two extents
        WHEN a PhiFlowBox is constructed
        THEN its getter returns a live PhiFlow Box covering them."""
        from phi.flow import Box

        box = PhiFlowBox(x=100.0, y=100.0)

        assert isinstance(box.get_box(), Box)

    def test_the_box_getter_is_stable(self):
        """GIVEN one PhiFlowBox
        WHEN its getter is called twice
        THEN it returns the same object.

        Wired into two grids, a box must be *one* domain: a getter that rebuilt it would give each
        grid its own, and nothing downstream would notice until the results disagreed."""
        box = PhiFlowBox(x=1.0, y=2.0)

        assert box.get_box() is box.get_box()

    def test_a_sphere_holds_a_phiflow_sphere(self):
        """GIVEN a centre and a radius
        WHEN a PhiFlowSphere is constructed
        THEN its getter returns a live PhiFlow Sphere."""
        from phi.flow import Sphere

        sphere = PhiFlowSphere(x=50.0, y=9.5, radius=5.0)

        assert isinstance(sphere.get_sphere(), Sphere)

    def test_a_cuboid_holds_a_phiflow_cuboid(self):
        """GIVEN a centre and a half-size
        WHEN a PhiFlowCuboid is constructed
        THEN its getter returns a live geometry.

        The constructor is the interesting part: it converts four scalars into the two `vec`s PhiFlow
        wants, which is exactly the translation a graph cannot do for itself."""
        cuboid = PhiFlowCuboid(center_x=50.0, center_y=30.0, half_size_x=10.0, half_size_y=5.0)

        assert cuboid.get_cuboid() is not None

    @pytest.mark.parametrize(
        "wrapper, kwargs, expected",
        [
            (PhiFlowBox, dict(x=100.0, y=50.0), "PhiFlowBox created: x=100.0, y=50.0"),
            (
                PhiFlowSphere,
                dict(x=1.0, y=2.0, radius=3.0),
                "PhiFlowSphere created: x=1.0, y=2.0, radius=3.0",
            ),
        ],
    )
    def test_construction_announces_itself(self, wrapper, kwargs, expected, capsys):
        """GIVEN a geometry wrapper
        WHEN it is constructed
        THEN it prints what it built — the line a user sees while a graph runs."""
        wrapper(**kwargs)

        assert expected in capsys.readouterr().out


class TestGridWrappers:
    """The two grids, and the unwrap branch they each carry."""

    @pytest.fixture
    def domain(self):
        """A domain wrapper, as a graph would supply it."""
        return PhiFlowBox(x=100.0, y=100.0)

    def test_a_staggered_grid_accepts_a_wrapper(self, domain):
        """GIVEN a PhiFlowBox as the domain
        WHEN a PhiFlowStaggeredGrid is constructed
        THEN it unwraps the box and builds a grid sampled at the cell faces.

        This is the branch a graph always takes: the domain arrives as the wrapper a constructor node
        produced. Note what identifies the result — PhiFlow's `StaggeredGrid` is a *factory function*,
        not a class, and both grid wrappers return the same `Field` type; the sampling location is what
        tells them apart."""
        from phi.field import Field

        grid = PhiFlowStaggeredGrid(domain, resolution_x=8, resolution_y=8).get_grid()

        assert isinstance(grid, Field)
        assert grid.is_staggered

    def test_a_staggered_grid_accepts_a_raw_geometry(self, domain):
        """GIVEN a raw PhiFlow Box rather than the wrapper
        WHEN a PhiFlowStaggeredGrid is constructed
        THEN it uses it as the domain directly, producing the same grid.

        The other half of the `isinstance` in the constructor. No graph reaches it today — a graph can
        only produce the wrapper — so a unit test is the only thing that can."""
        wrapped = PhiFlowStaggeredGrid(domain, 8, 8).get_grid()
        raw = PhiFlowStaggeredGrid(domain.get_box(), 8, 8).get_grid()

        assert raw.shape == wrapped.shape
        assert raw.is_staggered

    def test_a_centered_grid_accepts_a_wrapper(self, domain):
        """GIVEN a PhiFlowBox as the domain
        WHEN a PhiFlowCenteredGrid is constructed
        THEN it unwraps the box and builds a grid sampled at the cell centres."""
        from phi.field import Field

        grid = PhiFlowCenteredGrid(domain, resolution_x=8, resolution_y=8).get_grid()

        assert isinstance(grid, Field)
        assert not grid.is_staggered

    def test_a_centered_grid_accepts_a_raw_geometry(self, domain):
        """GIVEN a raw PhiFlow Box
        WHEN a PhiFlowCenteredGrid is constructed
        THEN it uses it directly — the same untaken branch as the staggered grid's."""
        wrapped = PhiFlowCenteredGrid(domain, 8, 8).get_grid()
        raw = PhiFlowCenteredGrid(domain.get_box(), 8, 8).get_grid()

        assert raw.shape == wrapped.shape
        assert not raw.is_staggered

    def test_the_two_grids_differ_only_in_where_they_sample(self, domain):
        """GIVEN the same domain and resolution
        WHEN both grid wrappers are constructed
        THEN both are `Field` objects, one sampled at faces and one at centres.

        Worth knowing before trusting a type check anywhere: these two are the *same Python class*, so
        nothing downstream can tell them apart with `isinstance`. `phiflow_iterate` takes one of each
        and dispatches on the **wrapper** type instead — and once unwrapped, a swapped pair would pass
        straight through to the solver."""
        staggered = PhiFlowStaggeredGrid(domain, 8, 8).get_grid()
        centered = PhiFlowCenteredGrid(domain, 8, 8).get_grid()

        assert type(staggered) is type(centered)
        assert (staggered.sampled_at, centered.sampled_at) == ("face", "center")

    def test_the_resolution_arguments_are_positional_in_port_order(self, domain):
        """GIVEN a grid constructed with x and y resolutions given positionally
        WHEN the grid is built
        THEN it matches the same call made with keywords.

        The executor binds a node's inputs positionally, so the parameter *order* — domain, x, y — is
        the node's port order and part of what a graph depends on."""
        positional = PhiFlowStaggeredGrid(domain, 4, 8).get_grid()
        keyword = PhiFlowStaggeredGrid(domain, resolution_x=4, resolution_y=8).get_grid()

        assert positional.shape == keyword.shape

    def test_construction_announces_the_resolution(self, domain, capsys):
        """GIVEN a grid wrapper
        WHEN it is constructed
        THEN it prints the resolution it allocated."""
        PhiFlowStaggeredGrid(domain, 16, 32)

        assert "PhiFlowStaggeredGrid created: resolution=16x32" in capsys.readouterr().out
