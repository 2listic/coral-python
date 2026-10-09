from typing import Any, Dict, Tuple
from phi.flow import Box, Cuboid
from phi.flow import vec


class PhiFlowCuboid:
    """Wrapper for Cuboid geometry"""

    def __init__(self, center_x: float, center_y: float, half_size_x: float, half_size_y: float):
        self.cuboid = Cuboid(
            vec(x=center_x, y=center_y), half_size=vec(x=half_size_x, y=half_size_y)
        )
        print(
            f"PhiFlowCuboid created: center=({center_x}, {center_y}), half_size=({half_size_x}, {half_size_y})"
        )

    def get_cuboid(self) -> Any:
        return self.cuboid


class PhiFlowBox:
    """Wrapper for Box domain"""

    def __init__(self, x: float, y: float):
        self.box = Box(x=x, y=y)
        print(f"PhiFlowBox created: x={x}, y={y}")

    def get_box(self) -> Any:
        return self.box
