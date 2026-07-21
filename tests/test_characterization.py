"""Characterization tests (issue #16, plan Step 0.3).

Pin the *behaviour* of ``run`` — the executor's returned ``results`` dict and the key stdout lines —
for one small math graph and one small string graph. Together with the golden-registry tests, these
prove the plugin-modularization move preserves execution results, not just the registry schema.

They exercise ``WorkflowExecutor`` directly, so they hold across the atomic move; only the import is
repointed to ``coral_app`` when the flat modules are deleted.
"""

import math

from executor import WorkflowExecutor


def test_math_graph_results_and_stdout(workflow_files, capsys):
    """Math fixture graph pins results and stdout.

    GIVEN the math fixture graph float(2) -> math.sqrt -> math.sin -> print_result, with the
          ``math`` module loaded,
    WHEN the workflow is executed,
    THEN each node's result equals the exact computed value (print_result -> None) and the domain
         stdout lines for sqrt, sin, and the print appear verbatim.
    """
    executor = WorkflowExecutor(str(workflow_files["math"]), modules=["math"])
    results = executor.execute()

    expected_sqrt = math.sqrt(2.0)
    expected_sin = math.sin(expected_sqrt)

    assert results["1"] == 2.0            # float primitive "2" -> 2.0
    assert results["0"] == expected_sqrt  # math.sqrt(2.0)
    assert results["2"] == expected_sin   # math.sin(sqrt(2.0))
    assert results["3"] is None           # print_result returns None

    out = capsys.readouterr().out
    assert f"math.sqrt(2.0) = {expected_sqrt}" in out
    assert f"math.sin({expected_sqrt}) = {expected_sin}" in out
    assert f"Print: {expected_sin}" in out


def test_string_graph_results_and_stdout(temp_workflow_file, capsys):
    """StringProcessor graph pins results and stdout.

    GIVEN a graph that builds StringProcessor(prefix="Hello, "), concatenates "world", then feeds
          print_result, with the ``string`` module loaded,
    WHEN the workflow is executed,
    THEN the constructor holds the prefix, concatenation yields "Hello, world", print_result returns
         None, and the concatenate and print stdout lines appear verbatim.
    """
    workflow = {
        "workflow": {
            "nodes": {
                "prefix": {"type": "str", "value": "Hello, "},
                "text": {"type": "str", "value": "world"},
                "sp": {"type": "StringProcessor"},
                "cat": {"type": "StringProcessor.concatenate"},
                "out": {"type": "print_result"},
            },
            "edges": {
                # prefix feeds the constructor
                "e0": {"source": "prefix", "target": "sp", "source_output": 0, "target_input": 0},
                # instance is the first method input; text is the second
                "e1": {"source": "sp", "target": "cat", "source_output": 0, "target_input": 0},
                "e2": {"source": "text", "target": "cat", "source_output": 0, "target_input": 1},
                # concatenation result feeds print_result
                "e3": {"source": "cat", "target": "out", "source_output": 0, "target_input": 0},
            },
        }
    }
    path = temp_workflow_file(workflow)
    results = WorkflowExecutor(str(path), modules=["string"]).execute()

    assert results["prefix"] == "Hello, "
    assert results["text"] == "world"
    assert results["sp"].prefix == "Hello, "
    assert results["cat"] == "Hello, world"
    assert results["out"] is None

    out = capsys.readouterr().out
    assert "StringProcessor.concatenate('world') = 'Hello, world'" in out
    assert "Print: Hello, world" in out
