# TODO — prune the test suite

Findings from a test audit done during this issue (intermezzo, after step 4). **Not part of issue
#25's scope**: parked here until it becomes an issue of its own.

The two duplicates the audit found in *this issue's own* work were fixed in #25 —
`test_build_function_map_empty` and `test_build_class_map_empty` were removed from
`tests/test_plugins.py`, since `test_plugin_discovery.py::TestHostWithoutPlugins` asserts the same
contract more strongly. **Everything below is pre-existing** and was deliberately left alone.

Nothing here is *wrong*: the audit found no test asserting something false, and no contradiction
between tests. The problem is cost without return — ~20 tests that pass whether or not the code
works, and most of a 60s wall clock spent re-running the same graphs.

Measured state at audit time: **246 test functions** (250 collected after parametrization, post-fix)
across 12 files. The files written since issue #23 — `test_graph.py`, `test_nodeports.py`,
`test_builtin_nodes.py`, `test_plugin_discovery.py`, `test_core_contract.py` — are coherent and
non-overlapping, and are **not** the subject of this note.

## Findings

### 1. Twelve tests whose only assertions are tautologies

All of the form `isinstance(x, dict)`, `len(x) > 0`, `is not None`. They pass whether or not the
workflow computed a correct result.

| file | tests |
| --- | --- |
| `test_integration.py` | `test_obstacle_workflow_execution`, `test_smoke_plume_workflow_execution`, `test_default_workflow_execution`, `test_classes_workflow_execution`, `test_functions_workflow_execution`, `test_phiflow_workflows_with_phiflow_plugin`, `test_math_workflows_with_math_plugin`, `test_workflow_with_wrong_plugin` |
| `test_plugins.py` | `test_primitives_map_exists`, `test_phiflow_plugin_availability` |
| `test_registry.py` | `test_registry_file_is_valid_json` |

**Five of them run a full PhiFlow simulation to assert `isinstance(results, dict)`** — the single
largest avoidable cost in the suite.

### 2. The same workflows are executed two or three times over

`test_integration.py` runs the `math` graph in `test_math_workflow_execution`,
`test_math_workflows_with_math_plugin` and `test_math_workflow_produces_expected_types`; only the
last asserts anything about the values. The `obstacle` / `smoke_plume` graphs are likewise executed
by three tests each.

Note which way the redundancy points: **`test_characterization.py` is the only file that asserts the
math graph's actual numbers** (`math.sqrt(2.0)`, `math.sin(...)`). It is not redundant with the
integration tests — they are redundant with it.

### 3. `TestPluginAvailability` restates `TestBuildFunctionMap`, more weakly

In `test_plugins.py`, `test_math_plugin_available` asserts strictly less than
`test_build_function_map_math`; same for the string and phiflow members of that class.

### 4. `test_plugins.py`'s job has drifted from its docstring

It says "plugin loading and function/class mapping", but the file also holds:

- `TestWorkflowExecutorPluginLoading` (4 tests) — executor behaviour, i.e. `test_executor.py`'s job;
- `TestFunctionExecution` (3 tests) — calls the math plugin's arithmetic directly
  (`add_func(5.0, 3.0) == 8.0`). That tests the *plugin*, not the host, and no plugin package has
  tests of its own;
- `TestClassInstantiation` (3 tests) — same, for `Calculator` / `StringProcessor`.

### 5. Docstring style is split 159 / 87

GIVEN/WHEN/THEN holds everywhere except the four oldest files: `test_integration.py` (19 of 19
legacy), `test_plugins.py` (28 of 32 after the fix), `test_registry.py` (24 of 33),
`test_executor.py` (14 of 18).

## Decisions to take, when this is picked up

- **Delete or strengthen?** A tautological test can be removed, or given the assertion it should have
  had. Per test: `test_classes_workflow_execution` probably deserves a real assertion; a third re-run
  of the same PhiFlow graph probably deserves deletion.
- **Where do plugin-behaviour tests live?** Finding 4 implies either moving them to
  `packages/coral-plugin-*/tests/`, which no plugin has today, or accepting that the host suite tests
  plugin behaviour and saying so in the docstring.
- **Is the docstring convention retroactive?** Converting 87 docstrings is mechanical but touches
  every old file; leaving them is a visible inconsistency when reading the suite top to bottom.
- **What is the target wall clock?** ~60s today, dominated by PhiFlow. Worth deciding what it should
  be before choosing how aggressively to cut — and whether the `slow` marker (already used by
  `test_acceptance.py`) is the right tool rather than deletion.
