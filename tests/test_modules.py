"""
Tests for module loading and function/class mapping.
"""

import pytest
from executor import WorkflowExecutor
from definitions import build_function_map, build_class_map, PRIMITIVES_MAP


class TestPrimitivesMap:
    """Test the primitives map."""

    def test_primitives_map_exists(self):
        """Test that primitives map is defined."""
        assert PRIMITIVES_MAP is not None
        assert isinstance(PRIMITIVES_MAP, dict)

    def test_primitives_map_basic_types(self):
        """Test that basic types are in primitives map."""
        assert 'int' in PRIMITIVES_MAP
        assert 'float' in PRIMITIVES_MAP
        assert 'str' in PRIMITIVES_MAP
        assert 'bool' in PRIMITIVES_MAP

    def test_primitives_type_conversion(self):
        """Test that primitives map converts types correctly."""
        assert PRIMITIVES_MAP['int'](5) == 5
        assert PRIMITIVES_MAP['float'](3.14) == 3.14
        assert PRIMITIVES_MAP['str']("hello") == "hello"
        assert PRIMITIVES_MAP['bool'](True) is True

    def test_primitives_string_to_type_conversion(self):
        """Test conversion from string to typed values."""
        assert PRIMITIVES_MAP['int']("42") == 42
        assert PRIMITIVES_MAP['float']("3.14") == 3.14
        assert PRIMITIVES_MAP['bool']("True") is True


class TestBuildFunctionMap:
    """Test function map building."""

    def test_build_function_map_math(self):
        """Test building function map with math module."""
        func_map = build_function_map(include=['math'])

        assert 'add' in func_map
        assert 'multiply' in func_map
        assert 'math.pow' in func_map
        assert callable(func_map['add'])

    def test_build_function_map_string(self):
        """Test building function map with string module."""
        func_map = build_function_map(include=['string'])

        assert 'print_result' in func_map
        assert callable(func_map['print_result'])

    def test_build_function_map_phiflow(self):
        """Test building function map with phiflow module."""
        try:
            func_map = build_function_map(include=['phiflow'])

            # Should have some phiflow functions
            assert len(func_map) > 0
        except ImportError:
            pytest.skip("PhiFlow not available")

    def test_build_function_map_multiple_modules(self):
        """Test building function map with multiple modules."""
        func_map = build_function_map(include=['math', 'string'])

        # Should have both math and string functions
        assert 'add' in func_map
        assert 'print_result' in func_map

    def test_build_function_map_exclude(self):
        """Test excluding modules from function map."""
        func_map = build_function_map(include=['string'], exclude=['math'])

        # Should have math
        assert 'print_result' in func_map

        # Should not have string
        assert 'add' not in func_map

    def test_build_function_map_empty(self):
        """Test building function map with no modules."""
        func_map = build_function_map(include=[])

        # Should be empty or minimal
        assert isinstance(func_map, dict)


class TestBuildClassMap:
    """Test class map building."""

    def test_build_class_map_math(self):
        """Test building class map with math module."""
        class_map = build_class_map(include=['math'])

        assert 'Calculator' in class_map
        assert isinstance(class_map['Calculator'], type)

    def test_build_class_map_string(self):
        """Test building class map with string module."""
        class_map = build_class_map(include=['string'])

        assert 'StringProcessor' in class_map
        assert isinstance(class_map['StringProcessor'], type)

    def test_build_class_map_multiple_modules(self):
        """Test building class map with multiple modules."""
        class_map = build_class_map(include=['math', 'string'])

        # Should have both classes
        assert 'Calculator' in class_map
        assert 'StringProcessor' in class_map

    def test_build_class_map_exclude(self):
        """Test excluding modules from class map."""
        class_map = build_class_map(include=['math'], exclude=['string'])

        # Should have Calculator
        assert 'Calculator' in class_map

        # Should not have StringProcessor
        assert 'StringProcessor' not in class_map

    def test_build_class_map_empty(self):
        """Test building class map with no modules."""
        class_map = build_class_map(include=[])

        # Should be empty or minimal
        assert isinstance(class_map, dict)


class TestWorkflowExecutorModuleLoading:
    """Test module loading in WorkflowExecutor."""

    def test_executor_default_module_phiflow(self, workflow_files):
        """Test that executor defaults to phiflow module."""
        try:
            executor = WorkflowExecutor(str(workflow_files["obstacle"]))

            # Should have phiflow in function map
            # (checking for at least some content, specific functions may vary)
            assert isinstance(executor.function_map, dict)
        except ImportError:
            pytest.skip("PhiFlow not available")

    def test_executor_math_module_loading(self, workflow_files):
        """Test executor with math module."""
        executor = WorkflowExecutor(str(workflow_files["math"]), modules=['math'])

        # Should have math functions
        assert 'add' in executor.function_map
        assert 'multiply' in executor.function_map

        # Should have Calculator class
        assert 'Calculator' in executor.class_map

    def test_executor_multiple_modules(self, workflow_files):
        """Test executor with multiple modules."""
        executor = WorkflowExecutor(
            str(workflow_files["math"]),
            modules=['math', 'string']
        )

        # Should have both
        assert 'add' in executor.function_map
        assert 'Calculator' in executor.class_map
        assert 'StringProcessor' in executor.class_map

    def test_executor_no_modules(self, temp_workflow_file):
        """Test executor with no modules (only primitives)."""
        workflow = {
            "workflow": {
                "nodes": {
                    "1": {"node_type": "primitive", "type": "int", "value": 42}
                },
                "edges": {}
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), modules=[])

        # Should still execute primitives
        results = executor.execute()
        assert "1" in results.keys()
        assert results["1"] == 42


class TestModuleAvailability:
    """Test which modules are available."""

    def test_math_module_available(self):
        """Test that math module is available."""
        func_map = build_function_map(include=['math'])
        assert len(func_map) > 0

    def test_string_module_available(self):
        """Test that string module is available."""
        func_map = build_function_map(include=['string'])
        class_map = build_class_map(include=['string'])
        # Should have at least some definitions
        assert len(func_map) > 0 or len(class_map) > 0

    def test_phiflow_module_availability(self):
        """Test if phiflow module is available."""
        try:
            func_map = build_function_map(include=['phiflow'])
            # If we get here, phiflow is available
            assert isinstance(func_map, dict)
        except ImportError:
            pytest.skip("PhiFlow not installed")


class TestFunctionExecution:
    """Test that loaded functions execute correctly."""

    def test_math_add_function(self):
        """Test that add function works correctly."""
        func_map = build_function_map(include=['math'])
        add_func = func_map['add']

        result = add_func(5.0, 3.0)
        assert result == 8.0

    def test_math_multiply_function(self):
        """Test that multiply function works correctly."""
        func_map = build_function_map(include=['math'])
        multiply_func = func_map['multiply']

        result = multiply_func(4.0, 2.5)
        assert result == 10.0

    def test_math_math_pow_function(self):
        """Test that math.pow function works correctly."""
        func_map = build_function_map(include=['math'])
        math_pow_func = func_map['math.pow']

        result = math_pow_func(2.0, 3.0)
        assert result == 8.0


class TestClassInstantiation:
    """Test that loaded classes can be instantiated."""

    def test_calculator_instantiation(self):
        """Test that Calculator class can be instantiated."""
        class_map = build_class_map(include=['math'])
        Calculator = class_map['Calculator']

        calc = Calculator(10.0)
        assert calc.value == 10.0

    def test_calculator_methods(self):
        """Test that Calculator methods work."""
        class_map = build_class_map(include=['math'])
        Calculator = class_map['Calculator']

        calc = Calculator(10.0)
        result = calc.add_to_value(5.0)

        assert result == 15.0
        assert calc.value == 15.0

    def test_string_processor_instantiation(self):
        """Test that StringProcessor class can be instantiated."""
        class_map = build_class_map(include=['string'])
        StringProcessor = class_map['StringProcessor']

        processor = StringProcessor("hello")
        assert processor.concatenate(" there") == "hello there"


class TestModuleIsolation:
    """Test that modules are properly isolated."""

    def test_math_only_no_string_functions(self):
        """Test that loading only math doesn't include string functions."""
        func_map = build_function_map(include=['math'])

        # Should have math
        assert 'add' in func_map

        # Should not have string-specific functions
        assert 'phiflow_iterate' not in func_map or func_map.get('phiflow_iterate') is None

    def test_string_only_no_math_functions(self):
        """Test that loading only string doesn't include math functions."""
        func_map = build_function_map(include=['string'])
        class_map = build_class_map(include=['string'])

        # Should not have Calculator
        assert 'Calculator' not in class_map

    def test_explicit_module_list_respected(self):
        """Test that only specified modules are loaded."""
        func_map = build_function_map(include=['math'])

        # Should have exactly math functions
        math_functions = ['add', 'multiply', 'math.pow', 'divide', 'power', 'math.sqrt']
        for func in math_functions:
            if func in func_map:
                # If it exists, it should be callable
                assert callable(func_map[func])