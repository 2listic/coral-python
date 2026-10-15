from typing import Any

from phi.flow import ZERO_GRADIENT, CenteredGrid, StaggeredGrid

from ..geom._box import PhiFlowBox


class PhiFlowStaggeredGrid:
    """Wrapper for StaggeredGrid"""

    def __init__(self, domain_box: Any, resolution_x: int, resolution_y: int):
        if isinstance(domain_box, PhiFlowBox):
            domain = domain_box.get_box()
        else:
            domain = domain_box
        self.grid = StaggeredGrid(0, 0, domain, x=resolution_x, y=resolution_y)
        print(f"PhiFlowStaggeredGrid created: resolution={resolution_x}x{resolution_y}")

    def get_grid(self) -> Any:
        return self.grid


class PhiFlowCenteredGrid:
    """Wrapper for CenteredGrid"""

    def __init__(self, domain_box: Any, resolution_x: int, resolution_y: int):
        if isinstance(domain_box, PhiFlowBox):
            domain = domain_box.get_box()
        else:
            domain = domain_box
        self.grid = CenteredGrid(0, ZERO_GRADIENT, domain, x=resolution_x, y=resolution_y)
        print(f"PhiFlowCenteredGrid created: resolution={resolution_x}x{resolution_y}")

    def get_grid(self) -> Any:
        return self.grid
