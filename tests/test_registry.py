"""
Tests for registry generation and type conversion.
"""

import pytest
from registry import generate_registry, python_type_to_string, save_registry_to_file
from definitions import PRIMITIVES_MAP, build_function_map, build_class_map
from pathlib import Path
import json


def find_by_method_name(registry, method_name):
    """Helper to find registry entry by method_name."""
    for node_data in registry.values():
        if node_data.get('method_name') == method_name:
            return node_data
    return None


def find_by_type(registry, type_name):
    """Helper to find registry entry by type (for primitives and constructors)."""
    for node_data in registry.values():
        if node_data.get('type') == type_name:
            return node_data
    return None


def has_method_name(registry, method_name):
    """Check if registry contains an entry with given method_name."""
    return find_by_method_name(registry, method_name) is not None


def has_type(registry, type_name):
    """Check if registry contains an entry with given type."""
    return find_by_type(registry, type_name) is not None


class TestPythonTypeToString:
    """Test type hint to string conversion."""

    def test_basic_types(self):
        """Test conversion of basic Python types."""
        assert python_type_to_string(int) == "int"
        assert python_type_to_string(float) == "float"
        assert python_type_to_string(str) == "str"
        assert python_type_to_string(bool) == "bool"

    def test_none_type(self):
        """Test None type conversion."""
        assert python_type_to_string(type(None)) == "none"

    # def test_list_type(self):
    #     """Test list type conversion."""
    #     from typing import List
    #     assert python_type_to_string(list) == "list"
    #     assert python_type_to_string(List[int]) == "list"

    def test_unknown_type(self):
        """Test unknown type defaults to 'any'."""
        class CustomClass:
            pass
        assert python_type_to_string(CustomClass) == "any"


class TestRegistryGeneration:
    """Test registry generation for different modules."""

    def test_generate_registry_math_module(self):
        """Test registry generation for math module."""
        function_map = build_function_map(include=['math'])
        class_map = build_class_map(include=['math'])
        registry = generate_registry(function_map, list(PRIMITIVES_MAP.keys()), class_map)

        # Check for math functions
        assert has_method_name(registry, 'add')
        assert has_method_name(registry, 'multiply')
        assert has_method_name(registry, 'math.pow')

        # Check for Calculator class
        assert has_type(registry, 'Calculator')
        assert has_method_name(registry, 'Calculator.add_to_value')
        assert has_method_name(registry, 'Calculator.multiply_value')

    def test_generate_registry_phiflow_module(self):
        """Test registry generation for phiflow module."""
        try:
            function_map = build_function_map(include=['phiflow'])
            class_map = build_class_map(include=['phiflow'])
            registry = generate_registry(function_map, list(PRIMITIVES_MAP.keys()), class_map)

            # Check for PhiFlow definitions (using actual names from definitions)
            assert has_type(registry, 'PhiFlowBox') or has_method_name(registry, 'phiflow_union')
            # Registry should not be empty
            assert len(registry) > 0
        except ImportError:
            pytest.skip("PhiFlow not available")

    def test_generate_registry_primitives_always_included(self):
        """Test that primitives are always included in registry."""
        function_map = build_function_map(include=['math'])
        class_map = build_class_map(include=['math'])
        registry = generate_registry(function_map, list(PRIMITIVES_MAP.keys()), class_map)

        # Primitives should always be present
        assert has_type(registry, 'int')
        assert has_type(registry, 'float')
        assert has_type(registry, 'str')
        assert has_type(registry, 'bool')

    def test_generate_registry_multiple_modules(self):
        """Test registry generation with multiple modules."""
        function_map = build_function_map(include=['math', 'string'])
        class_map = build_class_map(include=['math', 'string'])
        registry = generate_registry(function_map, list(PRIMITIVES_MAP.keys()), class_map)

        # Should have both math and string entries
        assert has_method_name(registry, 'add')  # from math
        assert has_type(registry, 'StringProcessor')  # from string

    def test_generate_registry_empty_modules(self):
        """Test registry generation with no modules (only primitives)."""
        function_map = build_function_map(include=[])
        class_map = build_class_map(include=[])
        registry = generate_registry(function_map, list(PRIMITIVES_MAP.keys()), class_map)

        # Should have primitives
        assert has_type(registry, 'int')
        assert has_type(registry, 'float')

        # Should not have module-specific entries
        assert not has_method_name(registry, 'add')
        assert not has_type(registry, 'Calculator')


class TestRegistryStructure:
    """Test the structure of generated registry entries."""

    def test_primitive_entry_structure(self):
        """Test that primitive entries have correct structure."""
        function_map = build_function_map(include=[])
        class_map = build_class_map(include=[])
        registry = generate_registry(function_map, list(PRIMITIVES_MAP.keys()), class_map)
        int_entry = find_by_type(registry, 'int')

        assert int_entry is not None
        # Primitives have a different structure - they don't have 'arguments' field
        assert 'value' in int_entry
        assert 'inputs' in int_entry
        assert 'outputs' in int_entry
        assert 'node_type' in int_entry
        assert 'type' in int_entry
        assert int_entry['node_type'] == 'primitive'
        assert int_entry['outputs'] == [-1]

    def test_function_entry_structure(self):
        """Test that function entries have correct structure."""
        function_map = build_function_map(include=['math'])
        class_map = build_class_map(include=['math'])
        registry = generate_registry(function_map, list(PRIMITIVES_MAP.keys()), class_map)
        add_entry = find_by_method_name(registry, 'add')

        assert add_entry is not None
        assert 'arguments' in add_entry
        assert 'inputs' in add_entry
        assert 'outputs' in add_entry
        assert 'node_type' in add_entry
        assert add_entry['node_type'] == 'function'

        # add function has 2 inputs (a, b)
        assert len(add_entry['inputs']) == 2
        assert 0 in add_entry['inputs']
        assert 1 in add_entry['inputs']

    def test_constructor_entry_structure(self):
        """Test that constructor entries have correct structure."""
        function_map = build_function_map(include=['math'])
        class_map = build_class_map(include=['math'])
        registry = generate_registry(function_map, list(PRIMITIVES_MAP.keys()), class_map)
        calc_entry = find_by_type(registry, 'Calculator')

        assert calc_entry is not None
        assert 'arguments' in calc_entry
        assert 'inputs' in calc_entry
        assert 'outputs' in calc_entry
        assert 'node_type' in calc_entry
        assert calc_entry['node_type'] == 'constructor'
        assert calc_entry['outputs'] == [-1]

    def test_method_entry_structure(self):
        """Test that method entries have correct structure."""
        function_map = build_function_map(include=['math'])
        class_map = build_class_map(include=['math'])
        registry = generate_registry(function_map, list(PRIMITIVES_MAP.keys()), class_map)
        method_entry = find_by_method_name(registry, 'Calculator.add_to_value')

        assert method_entry is not None
        assert 'arguments' in method_entry
        assert 'inputs' in method_entry
        assert 'outputs' in method_entry
        assert 'node_type' in method_entry
        assert method_entry['node_type'] == 'method'

        # Method should have inputs (instance + parameters)
        assert len(method_entry['inputs']) >= 1

    def test_function_arguments_have_types(self):
        """Test that function arguments include type information."""
        function_map = build_function_map(include=['math'])
        class_map = build_class_map(include=['math'])
        registry = generate_registry(function_map, list(PRIMITIVES_MAP.keys()), class_map)
        add_entry = find_by_method_name(registry, 'add')

        assert add_entry is not None
        # Check arguments structure
        for arg in add_entry['arguments']:
            assert 'connection_type' in arg
            assert 'type' in arg
            assert arg['connection_type'] in ['input', 'output']


class TestRegistryFileOperations:
    """Test saving registry to file."""

    def test_save_registry_to_file(self, tmp_path):
        """Test saving registry to JSON file."""
        output_file = tmp_path / "test_registry.json"

        save_registry_to_file(str(output_file), modules=['math'])

        # Check file was created
        assert output_file.exists()

        # Check file contains valid JSON
        with open(output_file, 'r') as f:
            registry = json.load(f)

        assert has_method_name(registry, 'add')
        assert has_type(registry, 'Calculator')

    def test_save_registry_default_filename(self, tmp_path, monkeypatch):
        """Test saving registry with default filename."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        save_registry_to_file(modules=['math'])

        # Check default file was created
        default_file = tmp_path / "registry-py.json"
        assert default_file.exists()

    def test_registry_file_is_valid_json(self, tmp_path):
        """Test that saved registry is valid JSON."""
        output_file = tmp_path / "test_registry.json"
        save_registry_to_file(str(output_file), modules=['math'])

        # Should be able to load without errors
        with open(output_file, 'r') as f:
            data = json.load(f)

        assert isinstance(data, dict)
        assert len(data) > 0


class TestRegistryConsistency:
    """Test consistency between generated registries and loaded files."""

    def test_generated_registry_matches_saved_file(self, tmp_path):
        """Test that generating and saving produces the same registry."""
        output_file = tmp_path / "test_registry.json"

        # Generate registry
        function_map = build_function_map(include=['math'])
        class_map = build_class_map(include=['math'])
        generated = generate_registry(function_map, list(PRIMITIVES_MAP.keys()), class_map)

        # Save to file
        save_registry_to_file(str(output_file), modules=['math'])

        # Load from file
        with open(output_file, 'r') as f:
            saved = json.load(f)

        # Should be identical
        assert generated.keys() == saved.keys()

        # Spot check a few entries by comparing specific node IDs
        for node_id in generated.keys():
            assert generated[node_id] == saved[node_id]

    def test_existing_registry_files_valid(self, registry_files):
        """Test that existing registry files are valid."""
        for name, path in registry_files.items():
            if not path.exists():
                pytest.skip(f"Registry file {name} not found")

            with open(path, 'r') as f:
                registry = json.load(f)

            # Check basic structure
            assert isinstance(registry, dict)
            assert len(registry) > 0

            # Check each entry has required fields
            for entry_name, entry_data in registry.items():
                assert 'node_type' in entry_data, f"{entry_name} missing node_type"
                assert 'inputs' in entry_data, f"{entry_name} missing inputs"
                assert 'outputs' in entry_data, f"{entry_name} missing outputs"

                # Primitives have different structure (no 'arguments', but have 'value' and 'type')
                if entry_data['node_type'] == 'primitive':
                    assert 'value' in entry_data, f"{entry_name} missing value"
                    assert 'type' in entry_data, f"{entry_name} missing type"
                else:
                    # Functions, constructors, and methods all have 'arguments'
                    assert 'arguments' in entry_data, f"{entry_name} missing arguments"


class TestModuleExclusionInclusion:
    """Test module inclusion/exclusion in registry generation."""

    def test_exclude_module(self):
        """Test excluding specific modules."""
        function_map = build_function_map(include=['math'], exclude=['string'])
        class_map = build_class_map(include=['math'], exclude=['string'])
        registry = generate_registry(function_map, list(PRIMITIVES_MAP.keys()), class_map)

        # Should have math
        assert has_method_name(registry, 'add')

        # Should not have string
        assert not has_type(registry, 'StringProcessor')

    def test_include_specific_module(self):
        """Test including only specific modules."""
        function_map = build_function_map(include=['math'])
        class_map = build_class_map(include=['math'])
        registry = generate_registry(function_map, list(PRIMITIVES_MAP.keys()), class_map)

        # Should have math
        assert has_method_name(registry, 'add')
        assert has_type(registry, 'Calculator')

    def test_primitives_not_excludable(self):
        """Test that primitives are always included."""
        function_map = build_function_map(include=[])
        class_map = build_class_map(include=[])
        registry = generate_registry(function_map, list(PRIMITIVES_MAP.keys()), class_map)

        # Primitives should still be there even with no modules
        assert has_type(registry, 'int')
        assert has_type(registry, 'float')
        assert has_type(registry, 'str')