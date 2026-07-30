# Plan: executor refactor

Implements [`architecture.md`](architecture.md). Read it first — it holds the reasoning; this file
holds the steps.

Steps are numbered in implementation order, which is not the stage order in `architecture.md`.
Bottom-up: build the port table first, then its two consumers, then the executor.

| step | what | architecture stage |
| --- | --- | --- |
| 1 | guard the current behaviour with tests | — |
| 2 | `nodeports.py` — the port table | 2 |
| 3 | `registry.py` reads the port table | 5 |
| 4 | `graph.py` — validate and order | 3 |
| 5 | `executor.py` — slim it | 4 |
| 6 | lock the separation, verify, document | — |

The registry (step 3) comes before the graph and the executor on purpose: it is the port table's
other consumer, the change is mechanical, and the golden files prove the port table is correct before
anything harder is built on it. If step 3 fails, the fault is in step 2.

Every step ends with the whole suite green.

New test docstrings use GIVEN/WHEN/THEN. Tests needing a specific plugin are tagged
`@pytest.mark.<plugin>`.

## 1. Guard the current behaviour

Today's ordering coverage is two cases (`tests/test_executor.py:238-271`). Add the missing ones
against the **current** code so the refactor is measured against real behaviour, not assumptions.

- [x] Add to `tests/test_executor.py::TestTopologicalSorting`, all asserting only on order:
  - [x] parallel edges — one primitive into both ports of `add`; must order, not deadlock
  - [x] diamond — one source, two branches, one sink
  - [x] isolated node — a node with no edges at all
  - [x] empty graph — no nodes, no edges
- [x] Run them. They must pass now; if one fails, the refactor's target behaviour has changed and
      that must be resolved before continuing.
- [x] Fix `circular_workflow_dict` (`tests/conftest.py:101`). Its `add` and `multiply` nodes have
      arity 2 but only one incoming edge each, so the fixture is invalid in two ways. Once validation
      is ordered as in step 4, check 4 fires before the cycle check and the message becomes an arity
      error — failing `test_cycle_detection`'s `match="Cycle detected"` (`tests/test_executor.py:270`).
  - [x] Add a primitive on port 1 of each node so arity is satisfied and the cycle is the only defect.
  - [x] Confirm the test still passes against the current code — it does, because neither cyclic node
        ever reaches in-degree 0.

Checked, no action needed: all 6 files in `tests/fixtures/valid_workflows/` and all other workflow
literals in `tests/*.py` pass the 7 validations, as does
`examples/phiflow/network-from-fe.json`.

## 2. The port table — `packages/coral-app/src/coral_app/nodeports.py`

- [x] Define the entry type: `kind` (`"primitive"` / `"function"` / `"constructor"` / `"method"`),
      `inputs` as a list of `(name, annotation)`, `outputs` as a list of annotations.
- [x] `build_port_table(function_map, class_map, primitives) -> dict[str, NodePorts]`, one entry per
      node type, keyed exactly as the graph's `type` field.
- [x] Derivation rules:
  - [x] function — `inspect.signature(func)`
  - [x] constructor — `inspect.signature(cls)`; already omits `self`; one output, the instance
  - [x] method — `inspect.signature(cls.method)`, **keeping `self`** as port 0
  - [x] primitive — no inputs, one output
  - [x] outputs from the return annotation: `Tuple[...]` gives one per element, `None` gives none,
        anything else gives one
- [x] Enumerate methods with the rules moved from `registry.py:106-113` — `dir(cls)`, skip
      underscore-prefixed, keep only `inspect.isfunction`.
- [x] `tests/test_nodeports.py`, using hand-written maps (no plugins, so nothing is skipped):
  - [x] one entry per function, class, `Class.method`, and primitive
  - [x] `self` is port 0 for methods, absent for constructors
  - [x] tuple return yields n outputs; `-> None` yields zero
  - [x] method enumeration skips underscore names and non-functions

## 3. Redirect `registry.py` to the port table

Mechanical. The golden files are the proof.

- [x] Split `_process_return_type` (`registry.py:25-49`): annotation → list of annotations moves to
      `nodeports.py`; list → numbered indices stays.
- [x] Rewrite `_add_function_node`, `_add_constructor`, `_add_methods` to read the port table instead
      of calling `inspect`. Same names, same output.
- [x] Keep unchanged in `registry.py`: `_create_input_argument`, `_create_output_argument`,
      `python_type_to_string`, the `inputs` list, output indices continuing after the inputs, `[-1]`
      for constructors and primitives.
- [x] **Keep the four emission loops in `registry.py`** — primitives (`:177`), functions (`:188`),
      all constructors (`:193`), then all methods (`:196`). The port table is a lookup, never the
      thing iterated. `tests/test_golden_registry.py:62` compares with `read_bytes()`, so the key
      order in `node_types.json` is pinned; iterating the table instead would reorder the keys and
      fail the comparison with identical content.
- [x] Confirm no `inspect` call remains in `registry.py` outside `python_type_to_string`.
- [x] Run `pytest tests/test_golden_registry.py`. All four golden files must match byte for byte. A
      diff here means the key order or the numbering moved, and must be put back.

## 4. The graph — `packages/coral-app/src/coral_app/graph.py`

- [ ] `Graph(nodes, edges, port_table)` plus `Graph.from_file(path, port_table)`. The port table
      arrives as plain data — no `inspect`, no plugin import in this module.
- [ ] Read the JSON as `executor.py:16-28` does today, including the `str()` coercion of edge
      endpoints.
- [ ] Validate, in this order, each raising `ValueError` naming the offending node or edge:
  - [ ] every edge `source` and `target` is a declared node — **before the sort**, because
        `TopologicalSorter` would otherwise invent a node for an unknown id
  - [ ] every node `type` has a port-table entry
  - [ ] per target node, the set of `target_input` values equals `{0 … n-1}` for n incoming edges
  - [ ] the incoming edge count equals the type's input count
  - [ ] `source_output` is valid: `0` or `-1` for a single-output type, `0 … n-1` for n > 1, and no
        outgoing edge at all from a zero-output type
  - [ ] edge type compatibility, per the table in `architecture.md` — skip whenever either side is
        `Any` or absent
  - [ ] no cycles
- [ ] Order with `graphlib.TopologicalSorter`, built as `{node: predecessors}` — the inverse
      direction of today's adjacency list at `executor.py:52`.
  - [ ] catch `CycleError` and re-raise `ValueError` including `args[1]`, the cycle path; keep the
        words "Cycle detected" so `tests/test_executor.py:270` still matches
  - [ ] `sorted()` each `get_ready()` batch, so the order follows the graph and not JSON key order
- [ ] Expose: `.order`, `.node(node_id)`, `.inputs_of(node_id)` returning incoming edges sorted by
      `target_input`. Build the incoming-edge index once, during validation — replacing the per-node
      re-filter of all edges at `executor.py:132`, `:180`, `:225`.
- [ ] `tests/test_graph.py`, all from JSON literals with hand-written port tables, no plugins:
  - [ ] the four ordering cases from step 1, now against `Graph`
  - [ ] cycle error names the cycle path
  - [ ] each of the seven validations rejects, one test per case, asserting on the message
  - [ ] `source_output` `-1` on a single-output type is accepted; `-1` on a multi-output type is
        rejected
  - [ ] type check skips when either side is `Any`; accepts `int` → `float`; rejects `str` → `float`
  - [ ] `inputs_of` returns edges sorted by `target_input`

## 5. Slim `executor.py`

- [ ] In `__init__`: keep the signature `(workflow_file, plugins=None)` so `cli.py` is untouched.
      Build the maps, then the port table, then `Graph.from_file`. Construction now validates, so a
      bad graph raises here, before any node runs.
- [ ] Replace the four branches (`:106`, `:126`, `:174`, `:218`) with one loop:
  - [ ] primitives convert and `continue`
  - [ ] collect input values once — `graph.inputs_of(node_id)`, read `self.results`, unwrap
        `source_output`
  - [ ] resolve the callable, three cases only: `function_map[type]`, `class_map[type]`,
        `getattr(values[0], method_name)` with `values[1:]` as the arguments
  - [ ] bind and call once: `params = list(inspect.signature(target).parameters)`, then
        `target(**dict(zip(params, args)))`
- [ ] Keep the method instance check at `:253`.
- [ ] Delete from `executor.py`: the arity checks (`:161`, `:204`, `:267`) — now done in `graph.py` —
      the `json` import, the adjacency list, `get_execution_order`, and all edge access.
- [ ] Update the two tests that reach for the old surface:
  - [ ] `test_simple_dag` (`:238`) — read `executor.graph.order` instead of
        `executor.get_execution_order()`
  - [ ] `test_cycle_detection` (`:265`) — wrap the `WorkflowExecutor(...)` construction in
        `pytest.raises`, since validation moved there
- [ ] Run the full suite.

## 6. Lock the separation, then finish

- [ ] Add to `tests/test_core_contract.py`, in the style of the existing
      `from __future__ import annotations` guard:
  - [ ] `graph.py` contains no `inspect`, no `discover`, no `load`, no plugin import
  - [ ] `executor.py` contains no `json`, no `graphlib`, no `self.edges`
- [ ] Re-run the wiring cases from `executor-ordering-analysis.md` and confirm each now raises before
      execution: `target_input` 3 and 9; two edges on port 0; `source_output` 7 on a scalar; an edge
      to an undeclared node id.
- [ ] `uv run pre-commit run --all-files`
- [ ] `pytest`
- [ ] `coral -p "math,string,phiflow" run examples/phiflow/network-from-fe.json` end to end — it must
      still execute; a rejection here is a bug in the new validation, not in the graph
- [ ] Verify a plugin subset still works: `uv pip uninstall coral-plugin-phiflow` then
      `uv run --no-sync pytest` — phiflow tests skip, nothing errors. Restore with `uv sync`.
- [ ] Update `CLAUDE.md`: the "Core components", "Data Flow", and "Node Execution Model" sections
      describe the old single-module executor.
