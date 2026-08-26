"""Tests for the coral-core Plugin contract (the ABC every plugin subclasses).

The contract must be *enforced*, not duck-typed: a subclass that omits either
abstract method cannot be instantiated. These tests pin that, plus the
project-wide ban on ``from __future__ import annotations`` (D3) — which would
stringize annotations and silently collapse every registry socket to ``"any"``.
"""

import ast
from pathlib import Path

import pytest
from coral_core import Plugin


class TestPluginContract:
    """The Plugin ABC enforces get_functions() / get_classes()."""

    def test_plugin_cannot_be_instantiated(self):
        """GIVEN the abstract Plugin base
        WHEN it is instantiated directly
        THEN a TypeError is raised (abstract methods unimplemented)."""
        with pytest.raises(TypeError):
            Plugin()

    def test_subclass_missing_get_classes_cannot_be_instantiated(self):
        """GIVEN a subclass that implements only get_functions()
        WHEN it is instantiated
        THEN a TypeError is raised (get_classes still abstract)."""

        class Partial(Plugin):
            def get_functions(self):
                return {}

        with pytest.raises(TypeError):
            Partial()

    def test_subclass_missing_get_functions_cannot_be_instantiated(self):
        """GIVEN a subclass that implements only get_classes()
        WHEN it is instantiated
        THEN a TypeError is raised (get_functions still abstract)."""

        class Partial(Plugin):
            def get_classes(self):
                return {}

        with pytest.raises(TypeError):
            Partial()

    def test_complete_subclass_can_be_instantiated(self):
        """GIVEN a subclass implementing both abstract methods
        WHEN it is instantiated and its methods called
        THEN it constructs and returns the declared maps."""

        class Complete(Plugin):
            def get_functions(self):
                return {"f": lambda: None}

            def get_classes(self):
                return {"C": int}

        plugin = Complete()
        assert plugin.get_functions().keys() == {"f"}
        assert plugin.get_classes() == {"C": int}


class TestStageSeparation:
    """Issue #23: one job per module, enforced structurally rather than by convention.

    The refactor split the old executor into stages — describe node types (``nodeports``), validate
    and order a graph (``graph``), execute it (``executor``). These guards pin the boundaries that
    make each stage independently testable: ``graph.py`` compares plain data, so it never
    introspects a callable or reaches for a plugin; ``executor.py`` receives an already-validated
    graph, so it never parses JSON, sorts, or walks the edge list.

    Only each file's *own* imports are inspected. ``graph.py`` importing ``NodePorts`` for a type
    annotation is the intended dependency on stage 2, even though stage 2 uses ``inspect`` itself.
    """

    def _source(self, module_name):
        root = Path(__file__).parent.parent
        path = root / "packages" / "coral-app" / "src" / "coral_app" / f"{module_name}.py"
        assert path.exists(), f"missing module: {path}"
        return path.read_text()

    def _imports(self, module_name):
        """The modules and the symbols a file imports."""
        tree = ast.parse(self._source(module_name), filename=module_name)
        modules, symbols = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.add(node.module or "")
                symbols.update(alias.name for alias in node.names)
        return modules, symbols

    def test_graph_does_not_introspect(self):
        """GIVEN graph.py
        WHEN its imports are parsed
        THEN `inspect` is absent — the port table arrives as plain data."""
        modules, _ = self._imports("graph")

        assert "inspect" not in modules

    def test_graph_does_not_reach_for_plugins(self):
        """GIVEN graph.py
        WHEN its imports are parsed
        THEN it imports no plugin and none of the host's plugin-loading machinery."""
        modules, symbols = self._imports("graph")

        assert not [name for name in modules if name.startswith("coral_plugin")]
        assert not symbols & {"discover", "load", "build_function_map", "build_class_map"}

    def test_executor_does_not_read_or_order_the_graph(self):
        """GIVEN executor.py
        WHEN its imports are parsed
        THEN neither `json` nor `graphlib` is there — reading and sorting belong to graph.py."""
        modules, _ = self._imports("executor")

        assert "json" not in modules
        assert "graphlib" not in modules

    def test_executor_does_not_introspect(self):
        """GIVEN executor.py
        WHEN its imports are parsed
        THEN `inspect` is absent — a node's arity comes from the port table, not from a fresh
        signature at run time."""
        modules, _ = self._imports("executor")

        assert "inspect" not in modules

    def test_executor_never_holds_the_edge_list(self):
        """GIVEN executor.py
        WHEN its source is read
        THEN it holds no `self.edges` — it asks the graph for a node's inputs instead."""
        assert "self.edges" not in self._source("executor")


class TestNoFutureAnnotations:
    """D3: no package source may `from __future__ import annotations`."""

    def _package_sources(self):
        root = Path(__file__).parent.parent
        return sorted((root / "packages").glob("*/src/**/*.py"))

    def test_sources_present(self):
        """GIVEN the workspace packages
        WHEN their source files are collected
        THEN at least one Python source exists to guard."""
        assert self._package_sources(), "no package sources found to check"

    def test_no_future_annotations_import(self):
        """GIVEN every package source file
        WHEN its imports are parsed
        THEN none imports `annotations` from __future__."""
        offenders = []
        for path in self._package_sources():
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                    if any(alias.name == "annotations" for alias in node.names):
                        offenders.append(str(path))
        assert not offenders, f"forbidden `from __future__ import annotations` in: {offenders}"
