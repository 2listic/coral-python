# Architecture: executor refactor

Target architecture agreed for issue #23. Findings that motivate it are in
[`executor-ordering-analysis.md`](executor-ordering-analysis.md). Implementation steps go in
`plan.md`.

## Constraints

1. **JSON formats are untouchable.** Both `node_types.json` (produced) and the editor's graph
   (consumed) are shared with other programs. Neither format changes.
2. **The graph is fully validated before execution starts.** Any wiring error fails loudly, before
   the first node runs. A long PhiFlow run must never be wasted on a bad graph.
3. **One job per module.**
4. **Prefer the standard library** — `graphlib` replaces the hand-rolled topological sort.

## Problem

`executor.py` (289 lines) interleaves five jobs: read the JSON, build and sort the graph, derive each
node's parameters, bind arguments, call. The `function` / `constructor` / `method` branches of
`execute()` (`executor.py:126`, `:174`, `:218`) repeat the same five steps:

| step | function | constructor | method |
| --- | --- | --- | --- |
| filter incoming edges | `:132` | `:180` | `:225` |
| sort by `target_input` | `:136` | `:181` | `:226` |
| read source results, unwrap `source_output` | `:140-154` | `:185-197` | `:234-246` |
| count inputs against parameters | `:161-165` | `:204-208` | `:267-271` |
| build kwargs and call | `:168-171` | `:211-214` | `:274-277` |

They differ at one point only: where the callable comes from — `function_map[...]` (`:129`),
`class_map[...]` (`:177`), `getattr(instance, method_name)` (`:260`).

## Stages

```
  plugins ──[1]──> maps ──[2]──> port table ──┬──[3]──> Graph ──[4]──> results
                                              │            ^
  graph JSON ─────────────────────────────────┼────────────┘
                                              │
                                              └──[5]──> node_types.json
```

| stage | job | input | output | module |
| --- | --- | --- | --- | --- |
| 1 | load plugins | plugin names | `function_map`, `class_map` | `coral_app/__init__.py` (exists) |
| 2 | describe each node type | the maps | port table | `coral_app/nodeports.py` (new) |
| 3 | read, validate, order the graph | graph JSON + port table | `Graph` | `coral_app/graph.py` (new) |
| 4 | execute | `Graph` + the maps | `results` | `coral_app/executor.py` (slimmed) |
| 5 | write the registry | port table | `node_types.json` | `coral_app/registry.py` (exists) |

## Stage 2 — the port table

One entry per node type, describing its connections: the input parameters (name and annotation) and
the outputs (annotations).

Derivation, all from `inspect.signature`:

| node type | inputs | outputs |
| --- | --- | --- |
| `add` (function) | `signature(add)` | return annotation: tuple gives n, `None` gives 0, otherwise 1 |
| `Calculator` (constructor) | `signature(Calculator)` — already omits `self` | 1, the instance |
| `Calculator.add_to_value` (method) | `signature(Calculator.add_to_value)` — **includes `self`**, which is port 0 | as above |
| `float` (primitive) | none | 1 |

Verified: `signature(cls)` and `signature(bound_method)` both omit `self`;
`signature(Class.method)` includes it, which is exactly the instance-at-port-0 convention.

Why this stage exists: stages 4 and 5 both need this information. Today they derive it separately —
`registry.py` in `_add_function_node` / `_add_constructor` / `_add_methods`, `executor.py` at
`:157`, `:200`, `:263` — which is how the two came to disagree about output numbering
(see the analysis, "Output-port numbering"). One table, no drift.

Stage 2 knows callables. It does not know what a graph or an edge is.

## Stage 3 — `Graph`

Takes the graph JSON and the port table. The port table arrives as plain data, so `graph.py` imports
neither `inspect` nor any plugin machinery, and its tests need no plugin installed.

Provides: the execution order, the node lookup, and each node's incoming edges sorted by
`target_input`. The executor asks for a node's inputs; it never sees the edge list.

Validation, all of it before any node runs:

1. every edge `source` and `target` names a declared node;
2. every node `type` has a port-table entry;
3. per target node, the set of `target_input` values equals `{0 … n-1}` for n incoming edges —
   catches two edges on one port and ports out of range;
4. the incoming edge count equals the type's input count — catches missing and extra connections;
5. every `source_output` is valid for the source type's output count (see below);
6. no cycles;
7. every edge's source output type is compatible with its target input type (see
   [Edge type validation](#edge-type-validation)).

Rule for check 4. **Every argument must be connected.** Default values declared in plugin code are
ignored — a node with a defaulted parameter left unwired is an error, not a request for the default.
This is already the implemented behaviour (`executor.py:161`, `:204`, `:267` compare edge count
against parameter count), confirmed by running a `Calculator` node with nothing connected:
`ValueError: Constructor Calculator expects 1 parameters but received 0 inputs`. Check 4 moves that
check earlier without changing it. Consequence for plugin authors: the defaults in `phiflow_union`,
`phiflow_iterate`, `phiflow_plot_and_save`, `Calculator`, and `StringProcessor` are unreachable from
a graph.

Rule for check 5. Both `0` and `-1` appear on the wire for a single-output node —
`examples/phiflow/network-from-fe.json` uses `0` for constructor outputs,
`tests/test_executor.py:220` uses `-1` — so both must be accepted:

| output count | accepted `source_output` |
| --- | --- |
| 1 | `0` or `-1` |
| n > 1 | `0 … n-1` |
| 0 (returns `None`) | none — the node has nothing to pass on |

`-1` on a multi-output type is rejected. Today it silently yields `result[-1]`, the last tuple
element (`executor.py:149`). No plugin callable lacks a return annotation, so a 0-output type really
does mean `-> None`.

Check 1 must precede the sort: `TopologicalSorter` silently materialises an unknown predecessor as a
node, so validating afterwards would admit a phantom node into the order.

Ordering uses `graphlib.TopologicalSorter` (`{node: predecessors}` — note the direction is the
inverse of today's adjacency list). `CycleError.args[1]` is the cycle path, so the raised error names
the cycle instead of only reporting that one exists. `CycleError` subclasses `ValueError`; the
re-raised message keeps the words "Cycle detected" so `tests/test_executor.py:270` still matches.
Nodes
within a ready batch are sorted, making the order a function of the graph rather than of JSON key
order; that batch is also where concurrent execution of independent branches would later hook in.

## Stage 4 — the executor

One job: walk the order `Graph` gives, collect each node's inputs from `results`, call, store.

The five repeated steps are written once. One three-way distinction remains — where the callable
comes from — and cannot be removed: a method's callable is produced by one of its own inputs and is
only known at run time.

No validation here. No `json`, no `graphlib`, no edge access.

## Output-port numbering

The editor and the executor number a node's outputs 0-based within outputs. `registry.py` numbers
them in a per-node space continuing after the inputs (`phiflow_iterate` → `[6, 7, 8]`), and writes
`[-1]` for primitives and constructors.

Resolution: **the editor's 0-based numbering is canonical** for validation, because the graph is what
gets validated. `node_types.json` keeps its current numbering unchanged — stage 2 supplies
annotations only; the numbering stays inside `registry.py`. `tests/golden/*.json` proves the output
is byte-identical.

## Out of scope

- **Sink pruning** — the executor runs every node, including branches feeding nothing. Cheap to add
  on top of this architecture later; not needed now.
- **Result lifetime** — `results` retains every intermediate value for the whole run. The
  predecessor counts `Graph` builds are the reference counts this would need.
- **`registry.py` internals** — a separate issue. This refactor only redirects it to stage 2.

## What `registry.py` gives up

Approved: `registry.py` switches to stage 2 in this refactor. Leaving it alone would make five
places deriving arity instead of four.

Moves to `nodeports.py`:

- enumerating which node types exist — `dir(cls)`, the underscore skip, the `inspect.isfunction`
  filter (`registry.py:106-113`);
- walking a signature for input parameters (`:59-61`, `:87-93`, `:118-129`);
- turning a return annotation into a list of output annotations — the `get_origin`/`get_args` logic
  inside `_process_return_type` (`:34-49`).

Stays in `registry.py` — every decision about the file format:

- `_create_input_argument` / `_create_output_argument` (`:11-22`), `python_type_to_string` (`:202`);
- all index numbering: the `inputs` list, output indices continuing after the inputs (`:37`, `:46`),
  `[-1]` for constructors and primitives (`:98`, `:182`);
- assembling the registry dict.

`_process_return_type` splits: annotation → list of annotations moves out, list → numbered indices
stays. The three `_add_*` functions keep their names and their output; their bodies stop calling
`inspect` and start reading the port table.

## Edge type validation

Stage 3 also check 7: the source's output annotation against the target's input annotation. This is
what protects a long run — a mismatch fails at t=0 instead of after the upstream node has executed.

The rule is deliberately narrow. When the answer is not certain, it skips:

| source | target | verdict |
| --- | --- | --- |
| `Any` or absent | anything | skip |
| anything | `Any` or absent | skip |
| same primitive | same primitive | accept |
| `bool` → `int`, `bool` → `float`, `int` → `float` | | accept — numeric widening |
| `str` → `float`, `int` → `str`, … | | **reject** |
| a class | the same class, or a base of it | accept |
| anything else | | skip |

Written by hand, not with a library. There is no standard-library subtype check: `issubclass`
handles classes only, not `Any`, unions, or generics. `typeguard` and `beartype` check a value
against an annotation, a different question. mypy's `is_subtype` is internal API. None of them is
worth a dependency for this table.

Skipping when unsure is required, not lazy. `issubclass(int, float)` is `False`, so a naive check
would reject an `int` primitive wired into a `float` parameter — valid and common. Wrongly refusing a
good graph is worse than not checking.

The check only sees what the plugins declare. Measured over all three plugins from the port table:
83 annotation slots, of which 59 are checkable (52 scalar, 7 class) and 24 are `Any`. They are
concentrated in one plugin:

| plugin | slots | `Any` | checkable |
| --- | --- | --- | --- |
| phiflow | 48 | 23 | 25 |
| math | 28 | 1 | 27 |
| string | 8 | 1 | 7 |

A slot is one input parameter or one output port; a method's port 0 is excluded, being the instance
rather than a declared argument. The per-plugin rows sum to 84 slots and 25 `Any` against 83 and 24
for the union: `print_result(value: Any) -> None` is declared by both `math` and `string`, and the
merged function map holds it once.

So `phiflow_iterate` returning `Tuple[Any, Any, Any]` cannot be checked, and a grid wired where a
float belongs would only fail after the simulation ran.

**Annotation quality is the plugin author's responsibility, not the host's.** The host provides the
check; how much it covers follows from what the plugin declares. A plugin that annotates its types
properly gets its wiring verified at t=0; a plugin that writes `Any` does not. Fixing
`coral-plugin-phiflow` is out of scope here — it is a plugin change, and it belongs to whoever owns
that plugin.

This is already the same bargain as the registry: `CLAUDE.md` states that type hints are required for
the registry to describe a node properly. The type check extends that requirement's payoff rather
than adding a new one.

Also kept: the existing `isinstance(instance, class_map[class_name])` check for method nodes
(`executor.py:253`). It checks a real value, and it catches the wrong object on a method's port 0.
It stays in the executor, where the value exists.
