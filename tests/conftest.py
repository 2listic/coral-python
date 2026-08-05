"""Fixtures for the repo-level suite.

Almost nothing is left here, and that is the point of issue #27. This directory now holds only tests
that **name no plugin**: the source-text invariants, the installed-plugin discovery contract, and the
wheel acceptance test. Everything that needed a plugin's name moved to that plugin's own package, and
everything about the host moved to ``packages/coral-app/tests`` where it runs against a designed
specimen.

Two things are gone on purpose:

* the ``pytest_collection_modifyitems`` hook that auto-skipped ``@pytest.mark.<plugin>`` tests. It
  existed to protect tests that named a plugin they did not own; no such test remains. A plugin's own
  suite guards itself in its own ``conftest.py``, keyed on its own entry point;
* the workflow/registry fixtures (``workflow_files``, ``load_workflow``, ``temp_workflow_file`` and the
  rest). The data they pointed at now ships with its owner, and each owner reads it from its own
  directory rather than through a shared table.
"""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    """The repo root, for tests that scan the workspace from disk."""
    return Path(__file__).parent.parent
