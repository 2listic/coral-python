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

**Deviations.**

- `primitives` is a **mapping** (`PRIMITIVES_MAP`), not a list of names: a primitive's output
  annotation is its Python type, which is what makes an edge out of a primitive checkable at all.
  `registry.py` never asks for primitive entries — it emits those from its own loop.
- `signature(cls)` needs a **fallback**. It raises `ValueError: no signature found for builtin type`
  on a C extension class, where the old `signature(cls.__init__)` did not. Both agree for all seven
  installed classes; the fallback to `__init__` minus `self` is what keeps `build_port_table` from
  raising on a C extension class, exactly as the old code did. What it produces, though, is not a
  usable constructor: such a class defines no `__init__` of its own, so this reads `object`'s —
  `(self, /, *args, **kwargs)` — and the entry records two `Any` inputs named `args`/`kwargs`. Graph
  check 4 then demands two incoming edges for it, and the call fails on the callable's own arguments
  (`datetime(2020, 1)` → `TypeError: function missing required argument 'day'`). So of the documented
  "C extension classes register a constructor, not methods", the *not methods* half holds exactly and
  the constructor is a placeholder. Preserved behaviour, not new behaviour: the old
  `signature(cls.__init__)` produced the same entry.
- A **missing annotation is normalised to `Any`**. Every consumer already treats "annotated `Any`" and
  "not annotated" alike — the registry writes `"any"` for both, the edge check skips both — and
  collapsing them here is what spares `graph.py` from importing `inspect` to recognise
  `Signature.empty`. The *return* annotation is still tested for `empty` before normalisation: there,
  absent means zero outputs while `-> Any` means one.
- **Staticmethods register as method nodes**, with an instance at port 0: `getattr(cls, name)` on a
  staticmethod yields a plain function, so the `inspect.isfunction` filter admits it. Pre-existing in
  `registry.py`, not introduced here; no installed plugin has one. A test pins it so the quirk stays
  recorded.
- **First writer wins on a key collision**, so the insertion order doubles as the precedence order
  `_classify` used: primitive > function > constructor > method. Keeps a dotted function name like
  `math.sqrt` a function.
- `methods_of(port_table, class_name)` added, so `registry.py` can enumerate a class's methods without
  reintroducing `inspect`.

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

**Deviations.**

- `_process_return_type` became **two** helpers, `_number_inputs` and `_number_outputs`, so the input
  side stops re-deriving its indices by hand in each of the three `_add_*` functions. Both take a
  `NodePorts` and return `(arguments, indices)`.
- A method's `self` argument is now rendered from the port table like any other input, rather than
  hardcoded as `_create_input_argument("self", class_name)`. It lands on `"any"` either way, since a
  class is not a key of `_REVERSE_PRIMITIVES_MAP` — which is why the goldens still match byte for byte.

## 4. The graph — `packages/coral-app/src/coral_app/graph.py`

- [x] `Graph(nodes, edges, port_table)` plus `Graph.from_file(path, port_table)`. The port table
      arrives as plain data — no `inspect`, no plugin import in this module.
- [x] Read the JSON as `executor.py:16-28` does today, including the `str()` coercion of edge
      endpoints.
- [x] Validate, in this order, each raising `ValueError` naming the offending node or edge:
  - [x] every edge `source` and `target` is a declared node — **before the sort**, because
        `TopologicalSorter` would otherwise invent a node for an unknown id
  - [x] every node `type` has a port-table entry
  - [x] per target node, the set of `target_input` values equals `{0 … n-1}` for n incoming edges
  - [x] the incoming edge count equals the type's input count
  - [x] `source_output` is valid: `0` or `-1` for a single-output type, `0 … n-1` for n > 1, and no
        outgoing edge at all from a zero-output type
  - [x] edge type compatibility, per the table in `architecture.md` — skip whenever either side is
        `Any` or absent
  - [x] no cycles
- [x] Order with `graphlib.TopologicalSorter`, built as `{node: predecessors}` — the inverse
      direction of today's adjacency list at `executor.py:52`.
  - [x] catch `CycleError` and re-raise `ValueError` including `args[1]`, the cycle path; keep the
        words "Cycle detected" so `tests/test_executor.py:270` still matches
  - [x] `sorted()` each `get_ready()` batch, so the order follows the graph and not JSON key order
- [x] Expose: `.order`, `.node(node_id)`, `.inputs_of(node_id)` returning incoming edges sorted by
      `target_input`. Build the incoming-edge index once, during validation — replacing the per-node
      re-filter of all edges at `executor.py:132`, `:180`, `:225`.
- [x] `tests/test_graph.py`, all from JSON literals with hand-written port tables, no plugins:
  - [x] the four ordering cases from step 1, now against `Graph`
  - [x] cycle error names the cycle path
  - [x] each of the seven validations rejects, one test per case, asserting on the message
  - [x] `source_output` `-1` on a single-output type is accepted; `-1` on a multi-output type is
        rejected
  - [x] type check skips when either side is `Any`; accepts `int` → `float`; rejects `str` → `float`
  - [x] `inputs_of` returns edges sorted by `target_input`

**Two decisions taken during this step**, both by the issue owner, and both now reflected in
[`architecture.md`](architecture.md#edge-type-validation):

1. **The type check rejects definite class mismatches.** The verdict table said "a class → the same
   class, or a base of it: accept" and then "anything else: skip", leaving class → unrelated class and
   class ↔ primitive undecided. Both reject: `PhiFlowBox → PhiFlowSphere`, `Calculator → float` and
   `none → float` are errors. No existing graph is affected — across the six fixtures and the phiflow
   example, all 148 edges are `Any`-involved (37) or an exact type match (111).
2. **`graph.py` names no coral type.** A hand-written scalar/widening table was rejected as invented
   knowledge: `PRIMITIVES_MAP` declares which types exist and nothing declares how they relate, so
   such a table would be a third, drifting source of truth. Everything decidable comes from
   `issubclass` over the plugins' own annotations (which also gives `bool` → `int` free); the single
   relation the class hierarchy cannot express — `int` accepted where `float` is expected, though
   `issubclass(int, float)` is `False` — comes from the standard library's `numbers` tower.

**Other deviations.**

- **Edges became a frozen `Edge` dataclass** rather than dicts, carrying their JSON key as `id` so
  every message names the culprit (`Edge 'e3' reads output 7 of node 'n'…`). `source_output` is
  `Optional[int]`, `None` meaning the key was omitted — which preserves the executor's "omitted means
  do not unwrap" behaviour exactly.
- **An omitted `source_output` is rejected on a multi-output type**, accepted on a single-output one.
  Which of three tuple elements was meant is not knowable, and the old code passed the whole tuple
  downstream.
- **Two structural checks added**, so a malformed graph raises a named `ValueError` instead of a
  `KeyError`: a node with no `type`, and an edge missing `source` / `target` / `target_input`.
- `ports_of(node_id)` added — it is what lets step 5 delete `_classify` entirely.
- `Graph` accepts edges as the JSON's id → edge mapping *or* a plain sequence, which keeps the tests
  readable.

## 5. Slim `executor.py`

- [x] In `__init__`: keep the signature `(workflow_file, plugins=None)` so `cli.py` is untouched.
      Build the maps, then the port table, then `Graph.from_file`. Construction now validates, so a
      bad graph raises here, before any node runs.
- [x] Replace the four branches (`:106`, `:126`, `:174`, `:218`) with one loop:
  - [x] primitives convert and `continue`
  - [x] collect input values once — `graph.inputs_of(node_id)`, read `self.results`, unwrap
        `source_output`
  - [x] resolve the callable, three cases only: `function_map[type]`, `class_map[type]`,
        `getattr(values[0], method_name)` with `values[1:]` as the arguments
  - [x] bind and call once: `params = list(inspect.signature(target).parameters)`, then
        `target(**dict(zip(params, args)))`
- [x] Keep the method instance check at `:253`.
- [x] Delete from `executor.py`: the arity checks (`:161`, `:204`, `:267`) — now done in `graph.py` —
      the `json` import, the adjacency list, `get_execution_order`, and all edge access.
- [x] Update the two tests that reach for the old surface:
  - [x] `test_simple_dag` (`:238`) — read `executor.graph.order` instead of
        `executor.get_execution_order()`
  - [x] `test_cycle_detection` (`:265`) — wrap the `WorkflowExecutor(...)` construction in
        `pytest.raises`, since validation moved there
- [x] Run the full suite.

**Deviations.**

- **Three** tests reached for the old surface, not two. `test_executor_with_file_path` asserted on
  `executor.nodes` / `executor.edges`, which no longer exist and which the step 6 guard forbids; it now
  asserts on `executor.graph.nodes` / `executor.graph.edges`.
- The four ordering tests added in step 1 also had to be repointed here, from
  `executor.get_execution_order()` to `executor.graph.order`. They were written against the *old*
  surface on purpose, so that step 1 measured the refactor against real behaviour — which is why they
  belong to step 1's commit and their repointing to this one.
- `execute()` delegates to three helpers — `_convert`, `_input_values`, `_resolve` — which keeps it a
  readable loop. `_resolve` is where the irreducible three-way distinction lives, and the only place a
  node's kind still matters at run time.

## 6. Lock the separation, then finish

- [x] Add to `tests/test_core_contract.py`, in the style of the existing
      `from __future__ import annotations` guard:
  - [x] `graph.py` contains no `inspect`, no `discover`, no `load`, no plugin import
  - [x] `executor.py` contains no `json`, no `graphlib`, no `self.edges`
- [x] Re-run the wiring cases from `executor-ordering-analysis.md` and confirm each now raises before
      execution: `target_input` 3 and 9; two edges on port 0; `source_output` 7 on a scalar; an edge
      to an undeclared node id.
- [x] `uv run pre-commit run --all-files`
- [x] `pytest`
- [x] `coral -p "math,string,phiflow" run examples/phiflow/network-from-fe.json` end to end — it must
      still execute; a rejection here is a bug in the new validation, not in the graph
- [x] Verify a plugin subset still works: `uv pip uninstall coral-plugin-phiflow` then
      `uv run --no-sync pytest` — phiflow tests skip, nothing errors. Restore with `uv sync`.
- [x] Update `CLAUDE.md`: the "Core components", "Data Flow", and "Node Execution Model" sections
      describe the old single-module executor.

**Also done in this step.**

- **`CLAUDE.md` gained a "Graph validation" section** — the seven checks in order, the
  every-argument-must-be-connected rule and which plugin defaults it makes unreachable, the
  `source_output` table, and the type-compatibility table. "Key Constraints" gained
  validate-before-executing and one-job-per-module entries, and its "No cycles" line now credits
  `graph.py`.
- **`architecture.md`'s annotation-coverage figures were corrected.** They read "80 slots, 49
  checkable, 31 `Any`", and the per-plugin table summed to 21 rather than 31. Measured from the port
  table: **83 slots, 59 checkable (52 scalar, 7 class), 24 `Any`** — 23 of the 24 in `phiflow`. The old
  count also predated step 4's decision 1, which is what makes the 7 class slots checkable.

**One commit beyond this plan.** `architecture.md`'s "Edge type validation" section was then
reconciled with what step 4 implemented: the verdict table gained the class-mismatch reject rows and
skip rows for unions and generic aliases, and the "written by hand, not with a library" framing was
replaced by the `numbers`-tower explanation. Each documented row is asserted against
`graph._is_compatible`.
