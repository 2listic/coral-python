from typing import Any, Dict, Tuple
from phi.flow import Sphere


class PhiFlowSphere:
    """Wrapper for Sphere geometry"""

    def __init__(self, x: float, y: float, radius: float):
        self.sphere = Sphere(x=x, y=y, radius=radius)
        print(f"PhiFlowSphere created: x={x}, y={y}, radius={radius}")

    def get_sphere(self) -> Any:
        return self.sphere
