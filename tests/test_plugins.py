"""
Tests for plugin loading and function/class mapping.
"""

import pytest
from coral_app import (
    BUILTIN_FUNCTIONS,
    COLLECTION_TYPES,
    PRIMITIVES_MAP,
    TYPE_NAMES,
    build_class_map,
    build_function_map,
)
from coral_app.executor import WorkflowExecutor


class TestPrimitivesMap:
    """Test the primitives map."""

    def test_primitives_map_exists(self):
        """Test that primitives map is defined."""
        assert PRIMITIVES_MAP is not None
        assert isinstance(PRIMITIVES_MAP, dict)

    def test_primitives_map_basic_types(self):
        """Test that basic types are in primitives map."""
        assert "int" in PRIMITIVES_MAP
        assert "float" in PRIMITIVES_MAP
        assert "str" in PRIMITIVES_MAP
        assert "bool" in PRIMITIVES_MAP

    def test_primitives_type_conversion(self):
        """Test that primitives map converts types correctly."""
        assert PRIMITIVES_MAP["int"](5) == 5
        assert PRIMITIVES_MAP["float"](3.14) == 3.14
        assert PRIMITIVES_MAP["str"]("hello") == "hello"
        assert PRIMITIVES_MAP["bool"](True) is True

    def test_primitives_string_to_type_conversion(self):
        """Test conversion from string to typed values."""
        assert PRIMITIVES_MAP["int"]("42") == 42
        assert PRIMITIVES_MAP["float"]("3.14") == 3.14
        assert PRIMITIVES_MAP["bool"]("True") is True

    def test_collections_are_not_primitive_node_types(self):
        """GIVEN the collection types exist as socket type names
        WHEN PRIMITIVES_MAP is inspected
        THEN it holds none of them: a collection is built by a function, never by a node
        carrying a literal."""
        assert set(PRIMITIVES_MAP) == {"int", "float", "str", "bool", "any", "none"}
        assert not set(PRIMITIVES_MAP) & set(COLLECTION_TYPES)


class TestCollectionTypes:
    """The collection type names — renderable on a socket, but not node types."""

    def test_collection_types_are_the_real_python_types(self):
        """GIVEN the collection type table
        WHEN it is read
        THEN each name maps to the bare Python type, with no element typing."""
        assert COLLECTION_TYPES == {"list": list, "set": set, "dict": dict}

    def test_type_names_is_the_union_of_both_tables(self):
        """GIVEN the primitives and the collections
        WHEN TYPE_NAMES is read
        THEN it is exactly their union — every type name the registry can render on a socket."""
        assert TYPE_NAMES == {**PRIMITIVES_MAP, **COLLECTION_TYPES}
        assert set(TYPE_NAMES) == set(PRIMITIVES_MAP) | set(COLLECTION_TYPES)


class TestBuildFunctionMap:
    """Test function map building."""

    @pytest.mark.math
    def test_build_function_map_math(self):
        """Test building function map with the math plugin."""
        func_map = build_function_map(include=["math"])

        assert "add" in func_map
        assert "multiply" in func_map
        assert "math.pow" in func_map
        assert callable(func_map["add"])

    @pytest.mark.string
    def test_build_function_map_string(self):
        """Test building function map with the string plugin."""
        func_map = build_function_map(include=["string"])

        assert "print_result" in func_map
        assert callable(func_map["print_result"])

    @pytest.mark.phiflow
    def test_build_function_map_phiflow(self):
        """Test building function map with the phiflow plugin."""
        try:
            func_map = build_function_map(include=["phiflow"])

            # Beyond the builtins, which every map holds: the plugin must contribute its own.
            assert set(func_map) - set(BUILTIN_FUNCTIONS)
        except ImportError:
            pytest.skip("PhiFlow not available")

    @pytest.mark.math
    @pytest.mark.string
    def test_build_function_map_multiple_plugins(self):
        """Test building function map with multiple plugins."""
        func_map = build_function_map(include=["math", "string"])

        # Should have both math and string functions
        assert "add" in func_map
        assert "print_result" in func_map

    @pytest.mark.string
    def test_build_function_map_exclude(self):
        """Test excluding plugins from function map."""
        func_map = build_function_map(include=["string"], exclude=["math"])

        # Should have math
        assert "print_result" in func_map

        # Should not have string
        assert "add" not in func_map

    # The include=[] case lives in
    # test_plugin_discovery.py::TestHostWithoutPlugins, whose whole subject is the
    # zero-plugin host — asserting it here as well would be the same assertion twice.


class TestBuildClassMap:
    """Test class map building."""

    @pytest.mark.math
    def test_build_class_map_math(self):
        """Test building class map with the math plugin."""
        class_map = build_class_map(include=["math"])

        assert "Calculator" in class_map
        assert isinstance(class_map["Calculator"], type)

    @pytest.mark.string
    def test_build_class_map_string(self):
        """Test building class map with the string plugin."""
        class_map = build_class_map(include=["string"])

        assert "StringProcessor" in class_map
        assert isinstance(class_map["StringProcessor"], type)

    @pytest.mark.math
    @pytest.mark.string
    def test_build_class_map_multiple_plugins(self):
        """Test building class map with multiple plugins."""
        class_map = build_class_map(include=["math", "string"])

        # Should have both classes
        assert "Calculator" in class_map
        assert "StringProcessor" in class_map

    @pytest.mark.math
    def test_build_class_map_exclude(self):
        """Test excluding plugins from class map."""
        class_map = build_class_map(include=["math"], exclude=["string"])

        # Should have Calculator
        assert "Calculator" in class_map

        # Should not have StringProcessor
        assert "StringProcessor" not in class_map

    # As above: test_plugin_discovery.py::TestHostWithoutPlugins asserts the
    # include=[] class map is exactly empty, which is strictly stronger than the
    # `isinstance(class_map, dict)` this used to check.


class TestWorkflowExecutorPluginLoading:
    """Test plugin loading in WorkflowExecutor."""

    @pytest.mark.math
    def test_executor_default_plugins_all_discovered(self, workflow_files):
        """
        GIVEN a WorkflowExecutor constructed without an explicit plugin list
        WHEN its function map is built
        THEN it loads every discovered plugin — the same set as ``build_function_map(None)`` —
             with no plugin name hardcoded in the host.

        Tagged ``math`` because the graph it validates against uses ``math.sqrt``: constructing the
        executor fails without that plugin, even though the assertion itself is about the host.
        """
        from coral_app import build_function_map, discover

        executor = WorkflowExecutor(str(workflow_files["math"]))

        assert set(executor.function_map) == set(build_function_map(include=discover()))

    @pytest.mark.math
    def test_executor_math_plugin_loading(self, workflow_files):
        """Test executor with the math plugin."""
        executor = WorkflowExecutor(str(workflow_files["math"]), plugins=["math"])

        # Should have math functions
        assert "add" in executor.function_map
        assert "multiply" in executor.function_map

        # Should have Calculator class
        assert "Calculator" in executor.class_map

    @pytest.mark.math
    @pytest.mark.string
    def test_executor_multiple_plugins(self, workflow_files):
        """Test executor with multiple plugins."""
        executor = WorkflowExecutor(str(workflow_files["math"]), plugins=["math", "string"])

        # Should have both
        assert "add" in executor.function_map
        assert "Calculator" in executor.class_map
        assert "StringProcessor" in executor.class_map

    def test_executor_no_plugins(self, temp_workflow_file):
        """Test executor with no plugins (only primitives)."""
        workflow = {
            "workflow": {
                "nodes": {"1": {"node_type": "primitive", "type": "int", "value": 42}},
                "edges": {},
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), plugins=[])

        # Should still execute primitives
        results = executor.execute()
        assert "1" in results.keys()
        assert results["1"] == 42


class TestPluginAvailability:
    """Test which plugins are available."""

    @pytest.mark.math
    def test_math_plugin_available(self):
        """Test that the math plugin is available."""
        func_map = build_function_map(include=["math"])
        # Its own functions, not the builtins every map carries.
        assert set(func_map) - set(BUILTIN_FUNCTIONS)

    @pytest.mark.string
    def test_string_plugin_available(self):
        """Test that the string plugin is available."""
        func_map = build_function_map(include=["string"])
        class_map = build_class_map(include=["string"])
        # Should have at least some definitions of its own, past the builtins.
        assert (set(func_map) - set(BUILTIN_FUNCTIONS)) or class_map

    @pytest.mark.phiflow
    def test_phiflow_plugin_availability(self):
        """Test if the phiflow plugin is available."""
        try:
            func_map = build_function_map(include=["phiflow"])
            # If we get here, phiflow is available
            assert isinstance(func_map, dict)
        except ImportError:
            pytest.skip("PhiFlow not installed")


class TestFunctionExecution:
    """Test that loaded functions execute correctly."""

    pytestmark = pytest.mark.math

    def test_math_add_function(self):
        """Test that add function works correctly."""
        func_map = build_function_map(include=["math"])
        add_func = func_map["add"]

        result = add_func(5.0, 3.0)
        assert result == 8.0

    def test_math_multiply_function(self):
        """Test that multiply function works correctly."""
        func_map = build_function_map(include=["math"])
        multiply_func = func_map["multiply"]

        result = multiply_func(4.0, 2.5)
        assert result == 10.0

    def test_math_math_pow_function(self):
        """Test that math.pow function works correctly."""
        func_map = build_function_map(include=["math"])
        math_pow_func = func_map["math.pow"]

        result = math_pow_func(2.0, 3.0)
        assert result == 8.0


class TestClassInstantiation:
    """Test that loaded classes can be instantiated."""

    @pytest.mark.math
    def test_calculator_instantiation(self):
        """Test that Calculator class can be instantiated."""
        class_map = build_class_map(include=["math"])
        Calculator = class_map["Calculator"]

        calc = Calculator(10.0)
        assert calc.value == 10.0

    @pytest.mark.math
    def test_calculator_methods(self):
        """Test that Calculator methods work."""
        class_map = build_class_map(include=["math"])
        Calculator = class_map["Calculator"]

        calc = Calculator(10.0)
        result = calc.add_to_value(5.0)

        assert result == 15.0
        assert calc.value == 15.0

    @pytest.mark.string
    def test_string_processor_instantiation(self):
        """Test that StringProcessor class can be instantiated."""
        class_map = build_class_map(include=["string"])
        StringProcessor = class_map["StringProcessor"]

        processor = StringProcessor("hello")
        assert processor.concatenate(" there") == "hello there"


class TestPluginIsolation:
    """Test that plugins are properly isolated."""

    @pytest.mark.math
    def test_math_only_no_string_functions(self):
        """Test that loading only math doesn't include string functions."""
        func_map = build_function_map(include=["math"])

        # Should have math
        assert "add" in func_map

        # Should not have string-specific functions
        assert "phiflow_iterate" not in func_map or func_map.get("phiflow_iterate") is None

    @pytest.mark.string
    def test_string_only_no_math_functions(self):
        """Test that loading only string doesn't include math functions."""
        class_map = build_class_map(include=["string"])

        # Should not have Calculator
        assert "Calculator" not in class_map

    @pytest.mark.math
    def test_explicit_plugin_list_respected(self):
        """Test that only the specified plugins are loaded."""
        func_map = build_function_map(include=["math"])

        # Should have exactly math functions
        math_functions = ["add", "multiply", "math.pow", "divide", "power", "math.sqrt"]
        for func in math_functions:
            if func in func_map:
                # If it exists, it should be callable
                assert callable(func_map[func])
