from typing import Any, Tuple
import math

# PhiFlow imports - external Python library
try:
    from phi.flow import (
        # Classes
        Box, Sphere, StaggeredGrid, CenteredGrid, Solve,
        # Functions
        jit_compile, resample, iterate, plot, batch,
        # Modules
        advect, fluid,
        # Constants
        ZERO_GRADIENT,
    )
    PHIFLOW_AVAILABLE = True
except ImportError:
    PHIFLOW_AVAILABLE = False
    print("Warning: PhiFlow not available. PhiFlow functions will not be registered.")


# PhiFlow wrapper classes and functions (simplified for smoke_plume.py example)
if PHIFLOW_AVAILABLE:

    class PhiFlowBox:
        """Wrapper for Box domain"""
        def __init__(self, x: float, y: float):
            self.box = Box(x=x, y=y)
            print(f"PhiFlowBox created: x={x}, y={y}")

        def get_box(self) -> Any:
            return self.box


    class PhiFlowSphere:
        """Wrapper for Sphere geometry"""
        def __init__(self, x: float, y: float, radius: float):
            self.sphere = Sphere(x=x, y=y, radius=radius)
            print(f"PhiFlowSphere created: x={x}, y={y}, radius={radius}")

        def get_sphere(self) -> Any:
            return self.sphere


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


    def phiflow_step(velocity_grid: Any, smoke_grid: Any, pressure_grid: Any, dt: float, use_jit: bool) -> Tuple[Any, Any, Any]:
        """Execute one simulation step with optional JIT compilation"""
        v = velocity_grid.get_grid() if isinstance(velocity_grid, PhiFlowStaggeredGrid) else velocity_grid
        s = smoke_grid.get_grid() if isinstance(smoke_grid, PhiFlowCenteredGrid) else smoke_grid
        p = pressure_grid

        inflow = Sphere(x=50, y=9.5, radius=5)
        inflow_rate = 0.2

        def step_impl(v, s, p, dt):
            s = advect.mac_cormack(s, v, dt) + inflow_rate * resample(inflow, to=s, soft=True)
            buoyancy = resample(s * (0, 0.1), to=v)
            v = advect.semi_lagrangian(v, v, dt) + buoyancy * dt
            v, p = fluid.make_incompressible(v, (), Solve('scipy-direct', 1e-3, x0=p))
            return v, s, p

        if use_jit:
            step_impl = jit_compile(step_impl)

        new_v, new_s, new_p = step_impl(v, s, p, dt)
        print(f"phiflow_step executed: dt={dt}, use_jit={use_jit}")
        return new_v, new_s, new_p


    def phiflow_iterate(velocity_grid: Any, smoke_grid: Any, time_steps: int, dt: float, substeps: int) -> Tuple[Any, Any, Any]:
        """Run multiple simulation steps using PhiFlow iterate"""
        v0 = velocity_grid.get_grid() if isinstance(velocity_grid, PhiFlowStaggeredGrid) else velocity_grid
        smoke0 = smoke_grid.get_grid() if isinstance(smoke_grid, PhiFlowCenteredGrid) else smoke_grid

        inflow = Sphere(x=50, y=9.5, radius=5)
        inflow_rate = 0.2

        @jit_compile
        def step(v, s, p, dt):
            s = advect.mac_cormack(s, v, dt) + inflow_rate * resample(inflow, to=s, soft=True)
            buoyancy = resample(s * (0, 0.1), to=v)
            v = advect.semi_lagrangian(v, v, dt) + buoyancy * dt
            v, p = fluid.make_incompressible(v, (), Solve('scipy-direct', 1e-3, x0=p))
            return v, s, p

        v_trj, s_trj, p_trj = iterate(step, batch(time=time_steps), v0, smoke0, None, dt=dt, substeps=substeps)
        print(f"phiflow_iterate executed: time_steps={time_steps}, dt={dt}, substeps={substeps}")
        return v_trj, s_trj, p_trj


    def phiflow_plot_and_save(smoke_trajectory: Any, output_filename: str, frame_time: int, fps: int, dpi: int) -> Any:
        """Plot smoke trajectory and save as animation"""
        anim = plot(smoke_trajectory, animate='time', frame_time=frame_time, show_color_bar=False)
        anim.save(output_filename, writer='ffmpeg', fps=fps, dpi=dpi)
        print(f"phiflow_plot_and_save: saved to {output_filename} (fps={fps}, dpi={dpi})")
        return anim


# Define the functions that can be called by nodes
def add(a: float, b: float) -> float:
    """Add two numbers"""
    result = a + b
    print(f"add({a}, {b}) = {result}")
    return result


def multiply(a: float, b: float) -> float:
    """Multiply a by b"""
    result = a * b
    print(f"multiply({a}, {b}) = {result}")
    return result


def print_result(value: Any) -> None:
    """Print the result with a message"""
    print(f"Print: {value}")


# Wrapper functions for math module with proper type hints
def math_sqrt(x: float) -> float:
    """Calculate the square root of x"""
    result = math.sqrt(x)
    print(f"math.sqrt({x}) = {result}")
    return result


def math_sin(x: float) -> float:
    """Calculate the sine of x (in radians)"""
    result = math.sin(x)
    print(f"math.sin({x}) = {result}")
    return result


def math_cos(x: float) -> float:
    """Calculate the cosine of x (in radians)"""
    result = math.cos(x)
    print(f"math.cos({x}) = {result}")
    return result


def math_pow(x: float, y: float) -> float:
    """Calculate x raised to the power y"""
    result = math.pow(x, y)
    print(f"math.pow({x}, {y}) = {result}")
    return result


def test_tuple_return(x: float, y: float) -> Tuple[float, float, float]:
    """Test function that returns a tuple of three values"""
    result1 = x + y
    result2 = x * y
    result3 = x - y
    print(f"test_tuple_return({x}, {y}) = ({result1}, {result2}, {result3})")
    return result1, result2, result3


class Calculator:
    """A simple calculator class"""
    def __init__(self, initial_value: float = 0.0):
        """Initialize calculator with an initial value"""
        self.value = initial_value
    
    def add_to_value(self, amount: float) -> float:
        """Add amount to stored value"""
        self.value += amount
        print(f"Calculator.add_to_value({amount}) = {self.value}")
        return self.value
    
    def multiply_value(self, factor: float) -> float:
        """Multiply stored value by factor"""
        self.value *= factor
        print(f"Calculator.multiply_value({factor}) = {self.value}")
        return self.value
    
    def get_value(self) -> float:
        """Get current value"""
        print(f"Calculator.get_value() = {self.value}")
        return self.value


class StringProcessor:
    """A class for string operations"""
    def __init__(self, prefix: str = ""):
        """Initialize with optional prefix"""
        self.prefix = prefix
    
    def concatenate(self, text: str) -> str:
        """Concatenate prefix with text"""
        result = self.prefix + text
        print(f"StringProcessor.concatenate('{text}') = '{result}'")
        return result
    
    def repeat(self, text: str, times: int) -> str:
        """Repeat text n times"""
        result = text * times
        print(f"StringProcessor.repeat('{text}', {times}) = '{result}'")
        return result


# Map class names to classes
CLASS_MAP = {
    # "Calculator": Calculator,
    # "StringProcessor": StringProcessor,
}

# Add PhiFlow wrapper classes if available
if PHIFLOW_AVAILABLE:
    CLASS_MAP.update({
        "PhiFlowBox": PhiFlowBox,
        "PhiFlowSphere": PhiFlowSphere,
        "PhiFlowStaggeredGrid": PhiFlowStaggeredGrid,
        "PhiFlowCenteredGrid": PhiFlowCenteredGrid,
    })


# Map function names to actual functions
FUNCTION_MAP = {
    # "add": add,
    # "multiply": multiply,
    "print_result": print_result,
    # External library functions (math module) - using wrappers with type hints and logging
    # "math.sqrt": math_sqrt,
    # "math.sin": math_sin,
    # "math.cos": math_cos,
    # "math.pow": math_pow,
    # # Test function for tuple returns
    # "test_tuple_return": test_tuple_return,
}

# Add PhiFlow wrapper functions if available
if PHIFLOW_AVAILABLE:
    FUNCTION_MAP.update({
        # PhiFlow wrapper functions - simplified API matching smoke_plume.py example
        "phiflow_step": phiflow_step,
        "phiflow_iterate": phiflow_iterate,
        "phiflow_plot_and_save": phiflow_plot_and_save,
    })

# Map primitive type names to Python types
PRIMITIVES_MAP = {
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "any": Any,
    "none": type(None),
}
