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
