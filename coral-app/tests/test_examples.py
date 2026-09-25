"""The examples this package ships really run.

``README.md`` tells a reader to type ``coral run examples/collections/list.json``, so something must
actually type it. Until this existed the demos could rot — a renamed builtin, a mis-numbered
``target_input`` — while the suite stayed green and the documented command failed for the user.

These execute, unlike ``test_graphs_validate.py`` which only constructs. That is affordable precisely
because they are the host's own graphs: list/set/dict operations on primitives, no plugin, no solver.
Each plugin runs its own examples in its own suite, where the cost is that plugin's to pay.

``plugins=[]`` is not a shortcut here, it is the assertion: these graphs need **no plugin at all**.
The CLI cannot express that (an empty ``-p`` means *every installed* plugin), so it is only checkable
from a test.
"""

import pytest
from coral_app.executor import WorkflowExecutor
from host_suite import EXAMPLES


def example_graphs():
    """One case per example graph shipped by this package, discovered from disk."""
    return [
        pytest.param(path, id=f"{path.parent.name}/{path.name}")
        for path in sorted(EXAMPLES.rglob("*.json"))
    ]


@pytest.mark.parametrize("path", example_graphs())
def test_example_executes_with_no_plugin(path):
    """GIVEN an example graph shipped with the host
    WHEN it is executed with no plugin selected
    THEN it runs to completion and every node it declares has a result.

    One result per node — rather than merely "did not raise" — is what catches a node left
    unreachable, since the executor only visits what the graph's order contains.
    """
    executor = WorkflowExecutor(str(path), plugins=[])

    results = executor.execute()

    assert set(results) == set(executor.graph.nodes)


def test_examples_were_found():
    """GIVEN the discovery glob above
    WHEN it runs against this package
    THEN it found example graphs, so this module is not silently covering nothing."""
    assert example_graphs(), f"no example graphs discovered under {EXAMPLES}"
