"""
Every graph shipped under ``examples/`` really runs.

The examples are user-facing: ``README.md`` and ``CLAUDE.md`` tell a reader to type
``coral run examples/collections/list.json``. Until this module existed nothing in the suite ever
opened them — the collection graphs under ``tests/fixtures/valid_workflows/`` are *separate files*
that merely happen to hold the same graphs today, and nothing requires them to stay identical. So a
demo could rot (a renamed builtin, a mis-numbered ``target_input``, a node type dropped from a
plugin) while the suite stayed green and the documented command failed for the user.

Cases are discovered from disk, so a new example file is covered the day it is added rather than the
day someone remembers to list it here. What a directory's examples *need* is the one thing that
cannot be discovered, hence ``EXAMPLE_SPECS``; ``test_every_example_directory_is_registered`` fails
loud when a new directory appears without an entry, because the alternative is silent
non-coverage — the very hole this module was written to close.
"""

from pathlib import Path

import pytest
from coral_app.executor import WorkflowExecutor

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

# Per example directory: the plugins its graphs need, and the markers its cases carry.
#
# ``plugins`` is the *minimal sufficient* selection rather than what the documented command loads
# (an omitted ``-p`` means every installed plugin). Minimal keeps ``pytest -m "not slow"`` free of
# the phiflow import, which is the whole point of being able to skip the slow case.
EXAMPLE_SPECS = {
    "collections": {"plugins": [], "marks": ()},
    "phiflow": {"plugins": ["phiflow"], "marks": (pytest.mark.phiflow, pytest.mark.slow)},
}


def _example_cases():
    """One parametrised case per example graph, tagged per its directory's spec."""
    cases = []
    for path in sorted(EXAMPLES_DIR.rglob("*.json")):
        spec = EXAMPLE_SPECS.get(path.parent.name)
        if spec is None:
            continue  # unregistered directory — reported by the registration test below
        cases.append(
            pytest.param(
                path,
                spec["plugins"],
                id=f"{path.parent.name}/{path.name}",
                marks=spec["marks"],
            )
        )
    return cases


def _example_directories():
    """The directories under ``examples/`` that actually contain graphs."""
    return sorted({path.parent.name for path in EXAMPLES_DIR.rglob("*.json")})


@pytest.mark.integration
@pytest.mark.parametrize("example, plugins", _example_cases())
def test_example_executes(example, plugins):
    """GIVEN a workflow graph shipped as a user-facing example
    WHEN it is executed with the plugins its directory declares
    THEN it runs to completion and produces a result for every node it declares.

    Asserting one result per node — rather than merely "did not raise" — is what catches a node
    that was silently left unreachable, since the executor only visits what the graph orders.
    """
    executor = WorkflowExecutor(str(example), plugins=plugins)
    results = executor.execute()

    assert set(results) == set(executor.graph.nodes)


def test_every_example_directory_is_registered():
    """GIVEN the directories under ``examples/`` that hold graphs
    WHEN they are compared against ``EXAMPLE_SPECS``
    THEN every one has an entry, so no example is skipped for want of a declared plugin set."""
    unregistered = [name for name in _example_directories() if name not in EXAMPLE_SPECS]

    assert not unregistered, (
        f"examples/{unregistered} hold graphs no test runs. Add an entry to EXAMPLE_SPECS naming "
        f"the plugins they need (and pytest.mark.slow if they are expensive)."
    )


def test_examples_were_found():
    """GIVEN the discovery glob this module is built on
    WHEN it runs against the repo
    THEN it found graphs — an empty parametrisation would otherwise pass as zero silent cases."""
    assert _example_cases(), f"no example graphs discovered under {EXAMPLES_DIR}"
