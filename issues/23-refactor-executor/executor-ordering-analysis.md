# Analysis: node ordering algorithm in `executor.py`

**Scope:** preliminary/abstract analysis. The actual modifications are to be applied on a more
up-to-date branch where file paths and layout may differ, so findings below are framed as properties
of the *algorithm and its boundaries* rather than of specific line numbers. Line references
(`executor.py:NN`) are from branch `ordering-algo` at commit `7409894` and serve only as pointers to
the code being described.

**Subject:** `WorkflowExecutor.get_execution_order()` — `executor.py:44-70`.

## Verdict

The implementation is a correct, textbook Kahn's algorithm. The core loop has no defects. Every
issue identified is at its *boundaries*: what it does not validate, what it does not report, and what
it is coupled to.

## What it gets right (invariants to preserve in the port)

1. **Edge-counted in-degree, not predecessor-counted** (`:52`). Parallel edges — one source feeding
   two input ports of the same target, a legitimate and common graph shape — increment in-degree
   twice and are decremented twice via two adjacency entries. Verified: a primitive wired into both
   ports of `add` orders correctly. A rewrite that "cleans up" the adjacency list into a `set`, or
   that dedupes `(source, target)` pairs, **silently breaks this** and deadlocks the node. This is
   the easiest regression to introduce during a port.
2. **Cycle detection by completeness check** (`:67`), not by exception during traversal. Self-loops
   are caught correctly (in-degree never reaches 0).
3. **Empty graph and isolated nodes** are handled: with no edges every node is a root and the order
   is well-defined.
4. **Ordering is deterministic for a given file** — the root queue and adjacency lists derive from
   JSON dict insertion order, which Python preserves.

## Weaknesses, ranked by impact

### 1. Silent port-mapping corruption — the algorithm orders nodes but never validates ports

The most serious gap, and architectural rather than a bug in the sort. The sort establishes *node*
order; argument binding elsewhere (`:135`, `:182`, `:229`) sorts incoming edges by `target_input` and
then maps them **positionally by rank, not by index value**. Nothing cross-checks the two.

Verified empirically against the current code:

| Graph | Expected | Actual |
| --- | --- | --- |
| Two edges into 2-arg `add` with `target_input` **3** and **9** | error (ports out of range) | accepted, executes, returns `12` |
| Two edges **both into `target_input` 0** of `add` | error (port 0 double-connected, port 1 unconnected) | accepted, executes, returns `12` |

In the second case the arity check passes because it counts *edges*, not *distinct ports*, and the
relative order of the two tied edges falls out of Python's stable sort — i.e. out of JSON edge order.
A malformed graph from the editor therefore produces a plausible-but-wrong number instead of an
error.

**Fix:** perform this in the same pass that builds the in-degree table. While walking edges, group
them by target and assert that each target's `target_input` set is exactly `{0..n-1}` (or `{0..n}`
for methods, where the instance occupies port 0) against the callee's arity. One extra pass over
data already being traversed, converting a wrong answer into a diagnostic.

### 2. Dangling edges raise `KeyError`, not a domain error

`graph[edge["source"]]` / `in_degree[edge["target"]]` (`:51-52`) assume both endpoints exist in
`self.nodes`. An edge to a nonexistent node raises a bare `KeyError: 'ghost'` (verified) — naming
neither the offending edge nor the fact that the graph is malformed.

Note the asymmetry that makes this reachable: edge endpoints are coerced with `str()` (`:26-27`) but
node dict keys are not normalized, so the two ID namespaces are only *incidentally* aligned. Any
future change to how node IDs are keyed (integer IDs, nested groups, namespaced subgraphs)
desynchronizes them and surfaces as this same opaque `KeyError`. Validate endpoints explicitly and
normalize both sides at a single chokepoint.

### 3. Cycle diagnostics are unusable at graph scale

`ValueError("Cycle detected in workflow!")` (`:68`) names nothing. The information is already in hand
and free: after the loop, every node with `in_degree > 0` is in a cycle or downstream of one.
Restricting to nodes whose unresolved predecessors are themselves unresolved isolates the actual
cycle members. For a user looking at a 40-node editor canvas, `cycle involves n12 → n19 → n12` versus
`cycle detected` is the whole difference.

### 4. Non-determinism *across* equivalent graphs, with visible side effects

Tie-breaking among simultaneously-ready nodes is arbitrary (JSON order). Because nodes here are
side-effecting — `print_result`, console output, PhiFlow simulations writing `.mp4`/`.gif` — two
semantically identical graphs differing only in serialization order produce differently-ordered
output. That makes integration tests order-fragile and reduces reproducibility. A stable secondary
sort key (node ID, or editor-declared position) costs nothing and makes execution order a function of
graph *semantics* rather than of file layout.

### 5. `queue.pop(0)` is O(V) per pop

`:59` makes the sort O(V² + E) instead of O(V + E). Irrelevant at 40 nodes; trivially fixed with
`collections.deque`. Worth doing in the port purely because it is free.

### 6. Quadratic edge rescanning outside the sort

A larger real cost than #5: `execute()` re-filters *all* edges once per node (`:131`, `:181`, `:228`)
— O(V·E), across three near-identical duplicated blocks. The in-degree pass should emit a
`target → incoming edges sorted by target_input` index once and hand it to execution. This also
collapses the three duplicated blocks into one accessor, which is the natural home for the port
validation from #1.

## Two design questions worth settling before the port

- **Eager whole-graph execution.** The Kahn order currently drives execution of *every* node,
  including nodes feeding nothing. With PhiFlow simulations in the graph, an orphaned or unused
  branch is minutes of wasted compute. If the platform designates output/sink nodes, the algorithm
  should first prune to the ancestor set of those sinks and then order that subgraph. Cheap to add
  now, awkward to retrofit.
- **`self.results` never releases.** Results are retained for the entire run (`:122` onward). PhiFlow
  grids are large, so a long graph holds every intermediate tensor alive simultaneously. The
  out-degree table Kahn already builds is exactly the reference count needed to drop a result once
  its last consumer has run.

## Replacing the hand-rolled sort with `graphlib.TopologicalSorter`

The stdlib `graphlib.TopologicalSorter` (Python 3.9+) can replace the hand-rolled Kahn loop, and it is
a clear improvement rather than a wash. `pyproject.toml` declares `requires-python = ">=3.12"`, so it
is unconditionally available with no new dependency.

### What it resolves for free

| Weakness above | Resolved? |
| --- | --- |
| #3 cycle diagnostics | **Yes, better than hand-rolled.** `CycleError.args[1]` is the actual cycle path: `['a', 'b', 'c', 'a']`. Self-loops report `['a', 'a']`. |
| #4 non-deterministic tie-break | **Yes.** The `prepare()` / `get_ready()` / `done()` interface yields ready *batches*; `sorted(ready)` per batch makes order a function of graph semantics rather than file layout. |
| #5 `pop(0)` O(V²) | **Yes.** O(V+E) internally. |
| #1's *invariant* (parallel-edge footgun) | **Removed.** `add("n3", "n1", "n1")` counts the predecessor twice and decrements twice (verified: `['n1', 'n3']`). Unlike the hand-rolled version, deduping predecessors into a `set` is *also* safe, because increment and decrement cannot desynchronise. The footgun disappears instead of needing to be documented. |

The batch interface is also the architectural unlock: `get_ready()` returns *all* currently-runnable
nodes, which is precisely the handle needed to execute independent PhiFlow branches concurrently. That
is substantially harder to retrofit onto a hand-rolled FIFO queue.

### What it does not solve

- **Port validation (#1 proper) is untouched.** `graphlib`'s model is node→node dependency only;
  `target_input` / `source_output` are invisible to it. The edge walk that groups incoming edges by
  target, validates each target's port set, and builds the index for argument binding remains
  necessary. `graphlib` replaces the sort, not the edge bookkeeping.
- **Dangling edges (#2) get *worse* unless endpoints are pre-validated.** `TopologicalSorter` silently
  materialises unknown predecessors as nodes: `add("n3", "n1", "ghost")` yields
  `['n1', 'ghost', 'n3']`, injecting a phantom node into the execution order. Today the bad ID raises
  `KeyError` at sort time, before anything runs. With `graphlib` the failure moves to
  `self.nodes[node_id]` inside `execute()` — later, further from the cause, and *after* upstream nodes
  have already executed and possibly written `.mp4` output. Endpoint validation must therefore run
  before the sorter is constructed. Since #1 needs the same pass, this is not extra work.
- **Sink pruning and result-lifetime management** (the two design questions above) are out of scope
  for `graphlib` either way.

### Porting hazards

1. **The graph direction is reversed.** `TopologicalSorter` takes `{node: predecessors}`; the current
   code builds `{source: [targets]}`, i.e. successors. Inverting this by mistake yields a perfectly
   valid *reversed* order, which then fails downstream with confusing "hasn't been executed yet"
   errors that point nowhere near the sort.
2. **`CycleError` subclasses `ValueError`** (verified), so the existing `pytest.raises(ValueError)` at
   `tests/test_executor.py:271` still catches it — but its message is `"nodes are in a cycle"`, so the
   `match="Cycle detected"` assertion fails. Catch and re-raise with the cycle path included: this
   keeps the test green *and* delivers #3.

### Shape of the replacement

```python
from graphlib import TopologicalSorter, CycleError

def get_execution_order(self) -> list[str]:
    # Validate endpoints first: graphlib would silently invent nodes for unknown IDs.
    for edge in self.edges:
        for role in ("source", "target"):
            if edge[role] not in self.nodes:
                raise ValueError(f"Edge {role} '{edge[role]}' is not a declared node")

    predecessors = {node_id: [] for node_id in self.nodes}
    for edge in self.edges:
        predecessors[edge["target"]].append(edge["source"])

    sorter = TopologicalSorter(predecessors)
    try:
        sorter.prepare()
    except CycleError as e:
        raise ValueError(f"Cycle detected in workflow: {' -> '.join(e.args[1])}") from e

    order = []
    while sorter.is_active():
        ready = sorter.get_ready()
        order.extend(sorted(ready))   # stable tie-break; also the parallel-execution seam
        sorter.done(*ready)
    return order
```

Net effect: the sort shrinks to a handful of lines and gains strictly better diagnostics,
determinism, and a concurrency seam. The work that actually reduces defects — port validation and the
incoming-edge index — remains to be written, and is where the port should concentrate its effort.

## Output-port numbering: registry and executor disagree (verified)

`registry.py` numbers a node's outputs in a per-node port space continuing after its inputs, while the
editor and the executor number them 0-based within outputs:

| Source | `phiflow_iterate` second output |
| --- | --- |
| `registry-py.json` (generated) | port **7** — outputs are `[6, 7, 8]`, after the 6 inputs |
| `network-from-fe.json` (editor) | `source_output=1` |
| `executor.py:148-151` | used as a direct tuple index → `result[1]` |

Executor and editor agree; the registry is the odd one out, publishing a numbering nobody consumes.
Consequences:

1. The obvious validation `source_output in registry[type]["outputs"]` would reject every currently
   valid edge (`0 not in [6, 7, 8]`).
2. The guard at `:150` (`source_output_idx < len(result)`) fails **silently**: a registry-numbered
   `source_output=7` on a 3-tuple falls through and passes the *whole tuple* downstream. Same for a
   non-zero `source_output` on a non-tuple result. Plausible-but-wrong instead of an error — the same
   failure mode as #1.

Inputs are consistent: registry `inputs` is `[0..n-1]` and matches the editor's `target_input`,
including `self` at 0 for methods.

Note also that the executor re-derives arity via `inspect.signature` (`:158`, `:203`, `:268`) instead
of reading the registry schema — two sources of truth for the same fact, which is how the divergence
above went unnoticed.

Resolving which numbering is canonical is a **platform contract question** (both the editor and the
generated `node_types.json` are on the wire to DealiiX), not a unilateral fix in this repo. Port
validation cannot be written correctly until it is answered, so it should be settled first.

## Proposed separation of concerns

Extract a `graph.py` that owns everything graph-related: JSON decode, endpoint and port validation,
ordering, and the incoming-edge index. The executor receives a `Graph` and never sees raw edges.

Enforced by three greppable facts in `executor.py`:

- no `json` / `graphlib` import;
- no `self.edges` access — only `graph.inputs_of(node)`;
- no structural raises.

The contract: if constructing a `Graph` succeeds, it is executable. That is what lets the executor
drop its defensive checks.

## Test coverage caveat

Current coverage of this algorithm is two cases (`tests/test_executor.py:239-272`): one linear DAG and
one cycle. Not covered: parallel edges, diamond dependencies, isolated nodes, dangling edges, and any
port-validation case. A rewrite would land essentially unguarded — that test class is where the port
should start.

## Reproducing the empirical findings

The behaviours in #1 and #2 were confirmed by constructing minimal graphs (`math` module only) and
calling `get_execution_order()` / `execute()` directly:

- one primitive → both `target_input` ports of `add` → orders correctly (invariant 1);
- two primitives → `add` at `target_input` 3 and 9 → executes silently, returns 12;
- two primitives → `add` both at `target_input` 0 → executes silently, returns 12;
- edge whose `target` is an undeclared node ID → `KeyError`.

The `graphlib` claims were confirmed separately against `TopologicalSorter` on Python 3.14.6:
duplicate-predecessor counting, phantom-node creation for undeclared predecessors, `CycleError.args`
contents for both a 3-cycle and a self-loop, level batching via `prepare()`/`get_ready()`/`done()`,
empty-graph handling, and `issubclass(CycleError, ValueError)`.
