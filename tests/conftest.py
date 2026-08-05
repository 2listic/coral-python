"""
Pytest configuration and fixtures for coral-python tests.
"""

import json
from pathlib import Path
from typing import Any, Dict

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def workflow_files(project_root: Path) -> Dict[str, Path]:
    """Return paths to all workflow JSON files."""
    fixtures_dir = project_root / "tests" / "fixtures" / "valid_workflows"
    host_graphs = project_root / "packages" / "coral-app" / "tests" / "graphs"
    return {
        "obstacle": fixtures_dir / "network-from-fe-obstacle.json",
        "smoke_plume": fixtures_dir / "network-from-fe-smoke_plume.json",
        "math": fixtures_dir / "network-from-fe-math.json",
        "classes": fixtures_dir / "network-from-fe-classes.json",
        "functions": fixtures_dir / "network-from-fe-functions.json",
        "default": fixtures_dir / "network-from-fe.json",
        # The three pure-collection graphs moved to their owner, `coral-app`, which validates and
        # runs them in its own suite (issue #27, step 4). These entries only keep the tests that
        # still read them working until step 6 deletes them; nothing new should be added here.
        "collections_list": host_graphs / "network-collections-list.json",
        "collections_dict": host_graphs / "network-collections-dict.json",
        "collections_set": host_graphs / "network-collections-set.json",
        # Named "collections" but it wires an `add` node, so it is math's graph, not the host's.
        "collections_math": fixtures_dir / "network-collections-math.json",
    }


@pytest.fixture
def load_workflow(workflow_files: Dict[str, Path]):
    """Factory fixture to load workflow JSON files."""

    def _load(name: str) -> Dict[str, Any]:
        """Load a workflow JSON file by name."""
        if name not in workflow_files:
            raise ValueError(f"Unknown workflow: {name}. Available: {list(workflow_files.keys())}")

        with open(workflow_files[name], "r") as f:
            return json.load(f)

    return _load


@pytest.fixture
def simple_workflow_dict() -> Dict[str, Any]:
    """Return a simple valid workflow for testing."""
    return {
        "workflow": {
            "nodes": {
                "node1": {"type": "int", "value": 5},
                "node2": {"type": "int", "value": 3},
                "node3": {"type": "add"},
            },
            "edges": {
                "edge1": {
                    "source": "node1",
                    "target": "node3",
                    "source_output": 0,
                    "target_input": 0,
                },
                "edge2": {
                    "source": "node2",
                    "target": "node3",
                    "source_output": 0,
                    "target_input": 1,
                },
            },
        }
    }


@pytest.fixture
def circular_workflow_dict() -> Dict[str, Any]:
    """Return a workflow whose *only* defect is a circular dependency.

    ``add`` and ``multiply`` both take two arguments, so each cyclic node also gets a primitive on
    port 1. Without those, the fixture is invalid twice over (arity *and* cycle) and the arity check
    — which runs first — would mask the cycle this fixture exists to exercise.
    """
    return {
        "workflow": {
            "nodes": {
                "node1": {"type": "add"},
                "node2": {"type": "multiply"},
                "p1": {"type": "float", "value": 1.0},
                "p2": {"type": "float", "value": 2.0},
            },
            "edges": {
                "edge1": {
                    "source": "node1",
                    "target": "node2",
                    "source_output": 0,
                    "target_input": 0,
                },
                "edge2": {
                    "source": "node2",
                    "target": "node1",
                    "source_output": 0,
                    "target_input": 0,
                },
                "edge3": {
                    "source": "p1",
                    "target": "node1",
                    "source_output": 0,
                    "target_input": 1,
                },
                "edge4": {
                    "source": "p2",
                    "target": "node2",
                    "source_output": 0,
                    "target_input": 1,
                },
            },
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
        with open(temp_file, "w") as f:
            json.dump(workflow_dict, f, indent=2)

        return temp_file

    return _create


@pytest.fixture(autouse=True)
def isolate_cwd(monkeypatch, tmp_path):
    """Run every test from a disposable working directory.

    Some workflows (e.g. the PhiFlow ones) write output files such as
    ``simulation.mp4`` to a path that is relative to the current directory.
    Pinning cwd to a per-test ``tmp_path`` guarantees those artifacts land in
    a throwaway location instead of polluting the project's main directory,
    while the JSON fixtures themselves stay untouched.
    """
    monkeypatch.chdir(tmp_path)


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


def _repo_plugin_names() -> list:
    """Plugin names this repo ships, from ``packages/coral-plugin-<name>`` (the source of truth)."""
    packages = Path(__file__).parent.parent / "packages"
    prefix = "coral-plugin-"
    return sorted(p.name[len(prefix) :] for p in packages.glob(f"{prefix}*"))


def pytest_collection_modifyitems(config, items):
    """Skip plugin-tagged tests whose plugin isn't installed in this environment.

    The suite runs against whatever plugins happen to be installed — the canonical fully-synced
    workspace, but also any subset. A test tagged ``@pytest.mark.<plugin>`` (e.g. ``math``) needs
    that plugin; when it isn't discoverable, skip it cleanly here instead of letting
    ``build_*_map`` raise ``LookupError`` mid-test. Keyed on the plugins the repo actually ships
    (``packages/coral-plugin-*``), so the guard tracks the plugin set automatically — no hardcoded
    catalog to keep in sync.
    """
    from coral_app import discover

    installed = set(discover())
    for name in _repo_plugin_names():
        if name in installed:
            continue
        skip = pytest.mark.skip(reason=f"plugin {name!r} not installed")
        for item in items:
            if name in item.keywords:
                item.add_marker(skip)
