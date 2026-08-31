# Plan: `source_output` asks the port table, not the value

Fixes [issue #31](https://github.com/2listic/coral-python/issues/31). That issue holds the
reproduction and the symptoms; the decisions reached in discussion are recorded below, then the
steps.

## The one-line diagnosis

`executor.py:_input_values` decides *whether a value is a bundle of outputs* from the value's runtime
type:

```python
if edge.source_output is not None:
    if isinstance(value, tuple) and edge.source_output < len(value):
        value = value[edge.source_output]
```

"How many outputs does this node have" is a **static** fact, settled in stage 2 from the return
annotation and stored in the port table. `isinstance(value, tuple)` asks a **runtime** question that
cannot distinguish "three outputs, bundled" from "one output that happens to be a tuple". Every
symptom in the issue follows from that one substitution.

`graph.py:_output_annotation` already answers the same question the right way:

```python
outputs = self.ports_of(edge.source).outputs
if len(outputs) == 1:
    return outputs[0]          # `None` (key omitted) and -1 both mean "the only output"
return outputs[edge.source_output]
```

The executor is the only place that does not. This is the same shape as PR #24's review finding 3 —
code re-deriving at run time what stage 2 already stored.

## Decisions

| # | question | decision | why |
| --- | --- | --- | --- |
| 1 | what decides whether we index into the value? | **the port table**: index iff the source type declares more than one output | the static fact is already stored; the runtime test cannot answer the question at all |
| 1a | should the executor re-check `source_output`'s range on a single-output node? | **no — validation stays the only check** | graph check 5 already rejects such an edge, so it cannot reach the executor. Re-checking duplicates check 5 and contradicts one-job-per-module |
| 2 | what if the returned value does not match the declared output count? | **check at the producing node**, right after the call | the only option that fires whether or not the port is wired, and that blames the *author of the function* rather than the graph — which is where the fault is. See [Decision 2 in full](#decision-2-in-full) |
| 2a | which arities are checked? | **only n > 1** | n == 1 is uncheckable (a bare `-> tuple` returning `(10, 20)` is legitimate); n == 0 is unreadable (check 5 rejects every outgoing edge of a 0-output node) |
| 2b | what does it raise? | **`ValueError`**, naming node id, type, declared count and what came back | consistency with `graph.py` and the executor's existing `"Node X hasn't been executed yet!"`. `TypeError` reads more naturally for "expected tuple, got int", but consistency is worth more than that nuance |
| 3 | degenerate tuple annotations | **reject in `build_port_table`** | see the table in [Decision 3 in full](#decision-3-in-full) — they currently produce 0 ports, or an `Ellipsis`-typed socket, silently |

Two principles the decisions serve, both stated by the project already:

- **Unambiguous.** `0`, `-1` and the omitted key are documented synonyms for "the only output"
  (`CLAUDE.md`, check 5). After decision 1 they *are* synonyms, rather than three different values.
- **Fail loud.** No mismatch between what a node declares and what it returns passes silently.

## Decision 2 in full

Decision 1 alone already turns the issue's Effect 2 into a bare `IndexError` — but only when the
graph happens to wire the missing port, and with an unhelpful message (`tuple index out of range`,
no node, no type). Two neighbouring mismatches would still be caught by nothing:

```
-> Tuple[Any, Any]  returning (10, 20, 30)   # extra element silently dropped
-> Tuple[Any, Any]  returning [10, 20]       # a list: value[0] works, right by luck
```

Three options were weighed:

| | what | consequence |
| --- | --- | --- |
| (i) | nothing extra — let the bare `IndexError` happen | cheapest; the two cases above stay silent; contradicts fail-loud |
| (ii) | check at the consuming edge, before indexing | good message, but only fires on wired ports — an unread mismatch still passes |
| **(iii)** | **check at the producing node, after the call** | **chosen** |

**(iii), chosen.** It costs one `if` per non-primitive node execution, and it is the only one that
makes the port table's claim about a node *true* rather than merely assumed. Its cost is that it is
the first run-time check on a node's **output** — a new category for the executor, which until now
checked only one thing about a value (a method's port 0 being an instance of its class).

**Nothing in the repo breaks.** The only two multi-output functions that exist are
`math.test_tuple_return -> Tuple[float, float, float]` (returns 3) and
`phiflow_iterate -> Tuple[Any, Any, Any]` (returns `v_trj, s_trj, p_trj`, 3). Both already agree with
their annotation, so the check is a guard against future plugins, not a migration.

## Decision 3 in full

What `_outputs_from_return` does with each tuple spelling today, verified in the interpreter:

| annotation | ports today | verdict |
| --- | --- | --- |
| `-> tuple` (bare, lowercase) | **1** | correct, and decision 1 makes it coherent — one output, passed whole. **No change** |
| `-> Tuple` (bare, `typing`) | **0** | wrong: `get_origin` is `tuple` but `get_args()` is `()`. Reads as "no outputs"; the author meant "returns a tuple" |
| `-> Tuple[()]` | **0** | same mechanism |
| `-> Tuple[Any, ...]` | **2**, the second being `Ellipsis` | worse: a variadic tuple has no static arity, and `Ellipsis` becomes a socket annotation the registry renders and check 6 reasons about |

`Tuple[Any, ...]` is not mentioned in the issue; it was found while checking the others.

Today a bare `-> Tuple` makes every outgoing edge fail check 5 with a message about *ports*, when the
fault is the *annotation*. Rejecting at stage 2 names the real cause.

**The cost, stated plainly**: this fires while the port table is built — at `coral register` and at
every `WorkflowExecutor` construction — so one badly annotated function in an installed plugin makes
the whole host fail, even for a graph that never touches that node. That is the intended behaviour
and it matches existing precedent: an installed-but-broken plugin already raises `ImportError` at
load, and the project rejects silent partial state. It is nonetheless a real behavioural change for
plugin authors, and it is why it was decided explicitly rather than assumed.

No annotation in the repo is affected — the three tuple returns in-tree are all well-formed.

---

## Steps

### Step 1 — `nodeports.py`: reject degenerate tuple returns

In `_outputs_from_return`, when `get_origin(return_annotation) is tuple`:

- `get_args()` empty (`Tuple`, `Tuple[()]`) → raise `ValueError`;
- `Ellipsis` among the args (`Tuple[Any, ...]`) → raise `ValueError`;
- otherwise unchanged.

The message must name the annotation and say what to write instead, e.g.

```
A tuple return must declare its elements: got `typing.Tuple`, write e.g. `Tuple[float, str]`
(or plain `tuple` for a single output carrying a tuple)
```

`_outputs_from_return` takes only the annotation, so it cannot name the function. Either thread the
callable's name in, or catch and re-raise at the `_function_ports` / `_method_ports` call sites — the
implementer picks, but **the final message must name the offending function**, or the failure is as
unhelpful as the one it replaces. Update the docstring, which currently says only "A `Tuple[...]`
return is one output per element".

Bare lowercase `tuple` must keep yielding one output — add it to the tests as a regression guard, it
is the case the whole fix hinges on.

### Step 2 — `executor.py`: `_input_values` asks the port table

```python
if len(self.graph.ports_of(edge.source).outputs) > 1:
    value = value[edge.source_output]
```

This replaces the whole `if edge.source_output is not None:` block. Note the deletions:

- **no `is not None` guard** — a multi-output node's `source_output` is guaranteed non-`None` by
  check 5, and a single-output node's is now never read;
- **no `isinstance(value, tuple)`** — the port table decides;
- **no `< len(value)` bound** — decision 2's check has already run on the producing node, so by the
  time this line indexes, the tuple is known to have exactly the declared length.

Update the docstring: it currently says "unwrapping the requested element of a tuple return", which
describes the bug. Say instead that a node with a single output port passes its value whole whatever
`source_output` says, and a multi-output node always indexes.

### Step 3 — `executor.py`: check the arity of a node's result

In `execute()`, immediately after `self.results[node_id] = target(*arguments)` (the primitive branch
returns early and is untouched — and a primitive declares one output anyway). Extract a small
private method rather than inlining, so the reason can be written down once:

```python
def _check_output_arity(self, node_id, node_type, ports, result):
    """A node declaring n > 1 outputs must return a tuple of exactly n.

    The port table's arity comes from an annotation, which is a claim by the function's author.
    Everything downstream — the registry's ports, check 5, check 6, and `_input_values`'
    indexing — trusts it. This is the one place it is confronted with what the function
    actually returned, so a wrong annotation fails here, at the node that declared it, rather
    than as an `IndexError` at some consumer's edge or not at all.
    """
```

Two failure messages, both naming the node and its type:

```
Node 3 (phiflow_iterate) declares 3 outputs but returned a tuple of 2
Node 3 (phiflow_iterate) declares 3 outputs but returned int
```

Raise `ValueError` (decision 2b). Check only `len(ports.outputs) > 1` (decision 2a).

### Step 4 — tests

Every new test's docstring follows the project's GIVEN/WHEN/THEN structure.

Two of the four behaviours below are the mutation guards the issue asks for: dropping the
`isinstance` clause and dropping the `< len(value)` bound must both now be caught.

**`tests/test_nodeports.py`** — one class for tuple return annotations:

| annotation | expected |
| --- | --- |
| `-> Tuple[int, str]` | 2 output ports (regression, already covered by `returns_triple`) |
| `-> tuple` | **1** output port, annotation `tuple` — the case the fix hinges on |
| `-> Tuple` | `ValueError`, message naming the function |
| `-> Tuple[()]` | `ValueError` |
| `-> Tuple[Any, ...]` | `ValueError` |

**`tests/test_executor.py`** — one class, `TestOutputPortResolution`:

1. *the three spellings agree* — `pair() -> tuple` returning `(10, 20)`, read with `source_output`
   omitted, `0`, and `-1`: all three deliver `(10, 20)` whole. This is the issue's Effect 1 and kills
   the `isinstance` mutant.
2. *multi-output still indexes* — `triple() -> Tuple[Any, Any, Any]` returning 3 values: ports 0/1/2
   deliver the three elements.
3. *short tuple is loud* — declares 3, returns 2 → `ValueError` from the producing node, whether or
   not port 2 is wired. This is Effect 2 and kills the `< len(value)` mutant.
4. *long tuple, and non-tuple, are loud* — declares 2 returns 3; declares 2 returns an `int`.

These need node types that no plugin provides. Build them by monkeypatching
`coral_app.executor.build_function_map` to return the ad-hoc map, then construct
`WorkflowExecutor(temp_file, plugins=[])` normally — that exercises the real `__init__`, so the port
table and the `Graph` are built by production code. (The issue's reproduction uses
`WorkflowExecutor.__new__` to bypass `__init__`; it is fine for a repro but should not enter the
suite, since it would stop testing exactly the construction path decision 3 now fails in.) Put the
helper in `tests/conftest.py` if a second test file needs it, local to `test_executor.py` otherwise.

The whole feature needs **no plugin**, so none of these tests carries a plugin marker.

### Step 5 — documentation

`CLAUDE.md`, three passages, all currently describing the buggy behaviour:

- **line ~329**, Node Execution Model step 1: "unwrapping the element the edge's `source_output`
  names when the value is a tuple" → the port table decides; a single-output node passes its value
  whole, a multi-output node always indexes.
- **line ~372**, the check-5 table: it already documents `0` / `-1` / omitted as synonyms. Add that
  the executor now honours that, so `source_output` on a single-output node is genuinely ignorable.
- **Node Execution Model**, after the four steps: record the output-arity check as the executor's
  *second* value-level check, next to the existing method-instance one — the paragraph that says
  "Method nodes keep one run-time check … it is the only check about a value" is now false and must
  be rewritten.

Add the degenerate-annotation rule to **Type Hint Requirements**: a tuple return must declare its
elements; bare `Tuple`, `Tuple[()]` and `Tuple[Any, ...]` are rejected; plain `tuple` means one
output carrying a tuple.

`docs/ONBOARDING.md` mentions neither, so it needs no change — confirm with a grep before closing.

---

## What does not change

- **Graph validation.** Checks 1-7 are untouched; check 5 keeps accepting `0` / `-1` / omitted for a
  single-output node. Decision 1a is precisely that the executor does not re-check what check 5
  already guarantees.
- **`_output_annotation` in `graph.py`.** It is already correct — it is the model step 2 copies.
- **The registry format.** `node_types.json` is rendered from the port table, which changes only by
  rejecting annotations that were producing wrong entries. Step 1 could in principle change a golden
  file; it does not, because no in-tree annotation is degenerate. `tests/test_golden_registry.py`
  passing unchanged is the confirmation.
- **Every existing graph** under `examples/` and `tests/fixtures/`. No node in them declares more
  than one output except through `test_tuple_return` and `phiflow_iterate`, both of which return
  their declared arity.

## Out of scope

- **A node returning a *longer* tuple than declared is caught, but the extra elements were never
  reachable anyway** — decision 2 makes it an error rather than a silent drop. That is as far as
  arity checking goes; nothing here validates the *types* of a tuple's elements against the declared
  annotations. Check 6 reasons about the declaration only, and continues to.
- **The phiflow plugin's 23 `Any` slots.** The issue notes that `phiflow_iterate -> Tuple[Any, Any, Any]`
  is unprotected by check 6. Decision 2 now guarantees its *arity*; its element types stay
  unchecked, and fixing that is a plugin change owned by whoever owns the plugin.
