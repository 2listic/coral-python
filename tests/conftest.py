"""
Pytest configuration and fixtures for coral-python tests.
"""

import pytest
import json
import os
from pathlib import Path
from typing import Dict, Any


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def workflow_files(project_root: Path) -> Dict[str, Path]:
    """Return paths to all workflow JSON files."""
    return {
        "obstacle": project_root / "network-from-fe-obstacle.json",
        "smoke_plume": project_root / "network-from-fe-smoke_plume.json",
        "math": project_root / "network-from-fe-math.json",
        "classes": project_root / "network-from-fe-classes.json",
        "functions": project_root / "network-from-fe-functions.json",
        "default": project_root / "network-from-fe.json",
    }


@pytest.fixture(scope="session")
def registry_files(project_root: Path) -> Dict[str, Path]:
    """Return paths to registry JSON files."""
    return {
        "math": project_root / "registry-math.json",
        "phiflow": project_root / "registry-phiflow.json",
        "mwe": project_root / "registry-py-mwe.json",
    }


@pytest.fixture
def load_workflow(workflow_files: Dict[str, Path]):
    """Factory fixture to load workflow JSON files."""
    def _load(name: str) -> Dict[str, Any]:
        """Load a workflow JSON file by name."""
        if name not in workflow_files:
            raise ValueError(f"Unknown workflow: {name}. Available: {list(workflow_files.keys())}")

        with open(workflow_files[name], 'r') as f:
            return json.load(f)

    return _load


@pytest.fixture
def load_registry(registry_files: Dict[str, Path]):
    """Factory fixture to load registry JSON files."""
    def _load(name: str) -> Dict[str, Any]:
        """Load a registry JSON file by name."""
        if name not in registry_files:
            raise ValueError(f"Unknown registry: {name}. Available: {list(registry_files.keys())}")

        with open(registry_files[name], 'r') as f:
            return json.load(f)

    return _load


@pytest.fixture
def simple_workflow_dict() -> Dict[str, Any]:
    """Return a simple valid workflow for testing."""
    return {
        "workflow": {
            "nodes": {
                "node1": {
                    "node_type": "primitive",
                    "type": "int",
                    "value": 5
                },
                "node2": {
                    "node_type": "primitive",
                    "type": "int",
                    "value": 3
                },
                "node3": {
                    "node_type": "function",
                    "method_name": "add"
                }
            },
            "edges": {
                "edge1": {
                    "source": "node1",
                    "target": "node3",
                    "source_output": 0,
                    "target_input": 0
                },
                "edge2": {
                    "source": "node2",
                    "target": "node3",
                    "source_output": 0,
                    "target_input": 1
                }
            }
        }
    }


@pytest.fixture
def circular_workflow_dict() -> Dict[str, Any]:
    """Return a workflow with circular dependency for testing cycle detection."""
    return {
        "workflow": {
            "nodes": {
                "node1": {
                    "node_type": "function",
                    "method_name": "add"
                },
                "node2": {
                    "node_type": "function",
                    "method_name": "multiply"
                }
            },
            "edges": {
                "edge1": {
                    "source": "node1",
                    "target": "node2",
                    "source_output": 0,
                    "target_input": 0
                },
                "edge2": {
                    "source": "node2",
                    "target": "node1",
                    "source_output": 0,
                    "target_input": 0
                }
            }
        }
    }


@pytest.fixture
def temp_workflow_file(tmp_path, simple_workflow_dict):
    """Create a temporary workflow JSON file."""
    def _create(workflow_dict: Dict[str, Any] = None) -> Path:
        """Create a temporary workflow file and return its path."""
        if workflow_dict is None:
            workflow_dict = simple_workflow_dict

        temp_file = tmp_path / "temp_workflow.json"
        with open(temp_file, 'w') as f:
            json.dump(workflow_dict, f, indent=2)

        return temp_file

    return _create


@pytest.fixture(autouse=True)
def reset_sys_path():
    """Ensure imports work correctly by adding project root to sys.path."""
    import sys
    project_root = Path(__file__).parent.parent

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    yield

    # Cleanup is optional since sys.path modifications are test-scoped


@pytest.fixture
def mock_print(monkeypatch):
    """Mock print function to capture output during tests."""
    printed_lines = []

    def _print(*args, **kwargs):
        printed_lines.append(" ".join(str(arg) for arg in args))

    monkeypatch.setattr("builtins.print", _print)
    return printed_lines