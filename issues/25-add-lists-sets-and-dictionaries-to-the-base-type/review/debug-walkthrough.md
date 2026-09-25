# Debugger walkthrough: the collection builtins

Step 1 of [`pr-28-review-plan.md`](pr-28-review-plan.md). Six stops that show every logic PR #28
adds, in the order the data moves. Each names a launch config, a file:line to break on, and the
question the stop answers — the point is to read the mechanism by executing it, not by reading it.

`.vscode/**` is gitignored, so the configs do not survive a fresh clone; this file is the durable
half. The configs it refers to are listed in [Launch configs](#launch-configs) at the end.

## What the app does, in one page

Two files, two audiences, and they never meet:

- **`node_types.json`, the registry** — a catalogue: every node type you can place, and what sockets
  it has. Written by `coral register`, read **only by the editor**. Coral never reads it back.
- **the graph JSON** — the assembled machine: which nodes were placed, and how they are wired.
  Written by the editor, read by `coral run`.

Nobody writes the catalogue by hand. `coral register` imports the plugins and reads each callable's
**signature** — parameter names, parameter annotations, return annotation. Type hints are not
decoration here: they are the only source the sockets have.

Then the word "type" means two different things, and keeping them apart explains most of this PR:

| | what it names | where it appears | examples |
| --- | --- | --- | --- |
| **node type** | which operation the node performs | a registry **key**; a node's `type` in a graph | `list_append`, `math.sqrt`, `Calculator`, `int` |
| **socket type** | what kind of value flows on a wire | inside a registry entry's `arguments` | `float`, `any`, `list` |

They are separate namespaces that share some spellings. `int` is both. `list` is **only** a socket
type — that is design decision 3, and stop 3 below is where you watch it happen. `any` means "unknown", so
both wiring checks (the editor's and `graph.py`'s check 6) switch off for that edge.

The five stages, in one line each: load the plugins → merge them into name→callable maps → derive one
**port table** entry per node type from the signatures → the registry renders that table into the
catalogue, and the executor walks a graph against it.

**Every line number below was verified reachable** by running the two entry points under `coverage`
and checking the target line appears in `executed_lines` — not by reading the code:

```bash
uv run --no-sync coverage run --source=coral_app -m coral_app.cli -p math run examples/collections/set.json
uv run --no-sync coverage run --source=coral_app -m coral_app.cli register --output=/tmp/nt.json
uv run --no-sync coverage json -o /tmp/cov.json    # then look up executed_lines per file
```

Result: `__init__.py:109`, `nodeports.py:103`, `graph.py:278`, `executor.py:60`, `executor.py:65` all
hit on the run; `registry.py:180-181` and `:185` hit on the register. `registry.py:177` is **not** hit
by either: it is the *missing* annotation branch (`inspect.Signature.empty`), and everything in the
math plugin and the builtins is annotated. An explicit `Any` does **not** go there — `Any` is a key of
`_TYPE_NAME_OF`, so `list_get`'s `Any` return returns `"any"` from line 181.

## The tour

### 1. Are the builtins really applied last?

**Config:** `coral: run a collections example`. **Break:** `packages/coral-app/src/coral_app/__init__.py:109`
— `function_map.update(BUILTIN_FUNCTIONS)`.

Inspect `function_map` before and after stepping that line. Before: only what the selected plugins
returned. After: 15 more keys.

Answers design decision 7 — a builtin cannot be shadowed. To see the rule bite rather than just run, watch
what happens with a plugin that declares `list_append`: the plugin's entry is in the dict at line 108
and gone at 109. The mutant that tests this is moving line 109 above the loop (step 4 of the plan).

### 2. What does a zero-input function node look like in the port table?

**Config:** same. **Break:** `nodeports.py:103` — the `NodePorts(...)` return in `_function_ports`.

This line runs for every function in the map, so break on a **condition** (gutter right-click → *Add
Conditional Breakpoint*). Only `func` and `sig` are in scope:

```python
not sig.parameters          # every zero-input function — selects on the property, not the name
func.__name__ == "set_new"  # just one (the Python name; a map key like math.sqrt is __name__ 'sqrt')
```

Or skip stopping altogether — a **logpoint** (*Add Logpoint*) prints and continues, giving the whole
table build as a trace:

```
{func.__name__}: {list(sig.parameters)} -> {sig.return_annotation}
```

What you should see:

```
set_new  -> NodePorts(kind='function', inputs=[],                                outputs=[set])
set_add  -> NodePorts(kind='function', inputs=[('s', set), ('item', typing.Any)], outputs=[set])
```

`inputs=[]` is the first function node with no inputs the platform will meet (primitives have none
either, but carry `outputs: [-1]`). The `Any` on `item` is the deliberate one — it is why an element
edge is never type-checked while the container edge is.

#### Reading the code

`NodePorts` is a frozen dataclass: a labelled 3-tuple (`kind`, `inputs`, `outputs`), no behaviour.
**A list position is a port number** — `inputs[2]` is the port an edge reaches with
`"target_input": 2`, `outputs[0]` is `"source_output": 0`. A method's port 0 is the instance,
synthesised here rather than read off the signature.

`sig.parameters` is an `OrderedDict` of `{name: Parameter}`, so the comprehension keeps the name and
replaces the `Parameter` with just its annotation:

```
sig.parameters.items()  [('s', <Parameter "s: set">), ('item', <Parameter "item: Any">)]
inputs                  [('s', set),                 ('item', typing.Any)]
```

It reads badly because it unpacks a pair whose first half is already *inside* the second
(`param.name == 's'`): `[(p.name, _annotation(p)) for p in sig.parameters.values()]` says the same
thing. `_annotation` only turns a *missing* annotation into `Any`.

A comprehension has no intermediate variable, so the variables pane stays empty until the object
exists. Use the Debug Console, then step over once and read the finished `NodePorts` in the pane:

```python
list(sig.parameters.items())
_outputs_from_return(sig.return_annotation)
```

### 3. Why does `list` render as `"list"` but `List[int]` as `"any"`?

**Config:** `coral: register (math, to /tmp)`. **Break:** `registry.py:180` — `if py_type in _TYPE_NAME_OF`.

This line runs once per socket — 66 times for `-p math` — so break on a condition. `py_type` is the
only name in scope:

```python
py_type in (list, set, dict)     # the three collections
py_type is list                  # just list
```

Without a condition you land on `float` and `Any` most of the time. Here is everything that actually
arrives, counted by spying on the function during a register:

```
  26  <class 'float'>      10  typing.Any          8  <class 'list'>
   7  <class 'set'>         7  <class 'dict'>      5  <class 'int'>
   3  <class 'coral_plugin_math.Calculator'>
```

**No generic alias is in that list, and that is the point:** `List[int]` never reaches the registry
today. No plugin annotates a node signature with one, and a `Tuple[...]` return is split into its
element annotations by the port table first — `Tuple[float, float, float]` arrives three times as
`float`, never as a tuple. To watch the generic branch you have to run the test that pins it:
`pytest -k test_parameterised_generic_is_any` ([`tests/test_registry.py:47-55`](../../../tests/test_registry.py#L47-L55)),
with the same breakpoint.

Inspect `_TYPE_NAME_OF`: nine entries, built by reversing `TYPE_NAMES` = `PRIMITIVES_MAP` (6) +
`COLLECTION_TYPES` (3). A bare `list` is a dict key, so it hits line 181. A `List[int]` is not, so it
falls through to line 185 and becomes `"any"`.

A logpoint is the cheaper way to see the whole stream at once:

```
{py_type} -> {_TYPE_NAME_OF.get(py_type, 'any')}
```

This is the whole of step 1 of `plan.md`, and the payoff is visible in the file it writes:

```json
"list_append": {"arguments": [{"connection_type": "input", "type": "list", "name": "lst"},
                              {"connection_type": "input", "type": "any",  "name": "item"}, ...]}
"list_new":    {"arguments": [{"connection_type": "output", "type": "list", "name": ""}],
                "inputs": [], "outputs": [0], "node_type": "function"}
```

Also confirm the platform bet from design decision 3 while you are here: `"list" in registry` is **False**.
`"list"` is a socket type with no entry of its own — the first such string in the format.

### 4. Which collection edges does validation actually check?

**Config:** `coral: run a collections example`. **Break:** `graph.py:278` — the `_is_compatible` call
in `_check_edge_types`.

This is check 6 of the seven validation checks, and validation runs while the `Graph` is
**constructed** — inside `WorkflowExecutor(...)`, before any node executes. So you arrive here with
`results` still empty. Per edge it compares two annotations from the port table: what the source's
chosen output port produces, and what the target's parameter at that port accepts. `_is_compatible`
skips whenever either side is `Any` (cannot judge → allow), accepts a class or a base of it, accepts
`bool → int` and `int → float`, rejects the rest.

No condition needed — `set.json` has 10 edges. In scope: `edge`, `source_annotation`, `ports`,
`target_name`, `target_annotation`. A logpoint saves the stepping:

```
{edge.id}: {source_annotation} -> {target_name}: {target_annotation}
```

`examples/collections/set.json` — node names are `SET_NODES` in `tests/test_integration.py`:

```
edge 0: node  4 ( set) -> node  5.s      ( set)  CHECKED
edge 1: node  0 ( int) -> node  5.item   ( Any)  skipped
edge 2: node  5 ( set) -> node  6.s      ( set)  CHECKED
edge 3: node  1 ( int) -> node  6.item   ( Any)  skipped
edge 4: node  6 ( set) -> node  7.s      ( set)  CHECKED
edge 5: node  2 ( int) -> node  7.item   ( Any)  skipped
edge 6: node  7 ( set) -> node  8.s      ( set)  CHECKED
edge 7: node  7 ( set) -> node  9.s      ( set)  CHECKED
edge 8: node  9 (list) -> node 10.lst    (list)  CHECKED
edge 9: node  3 ( int) -> node 10.index  ( int)  CHECKED
=> 7 checked, 3 skipped
```

The three skips are exactly the element ports. That is the honest size of what container typing buys:
the containers are verified, the payloads are not.

Then run it again on the interop fixture, because that is where the skip *matters*. Use the
**`coral: run the collections<->math interop fixture`** config (it needs `-p math`, and the fixture
lives outside `examples/`, so the picker config cannot reach it). The pytest route is
`pytest: one test (-k)` with `test_collection_feeds_a_plugin_function` — the name to filter on is the
test's, not the `collections_math` key that `conftest.py` uses internally.

```
edge 5: node  2 ( int) -> node  7.index  ( int)   CHECKED
edge 8: node  7 ( Any) -> node  9.a      (float)  skipped
edge 9: node  8 ( Any) -> node  9.b      (float)  skipped
=> 6 checked, 4 skipped
```

Nodes 7 and 8 are `list_get` feeding `add(a: float, b: float)`. The two edges that carry a value out of
a collection into a plugin — the whole point of the interop case — are the two nobody can check. Wire a
list of strings into `add` and it validates, then fails inside the plugin.

These same two edges are the ones the editor **rejects and drops**, which is finding 3 of
[`pr-28-review-round-2.md`](pr-28-review-round-2.md) — worth reading next to this stop, since the two
validators disagree precisely here.

### 5. Purity, on the object

**Config:** `coral: run a collections example` (set). **Break:** `executor.py:65` —
`self.results[node_id] = target(*arguments)`.

At node `6` (`with_seven`), inspect `arguments[0]` — the set produced by node `5` — and `id()` it.
Step over. Inspect `self.results['5']` again: same object, same contents, and `self.results['6']` is
a different object. Nothing was mutated.

`executor.py:60` (`_input_values`) is the companion stop, showing the values arriving already in port
order.

### 6. Why purity matters — the fan-out

Same config and breakpoint, but continue to node `7` (`with_duplicate`), whose result is read by
**two** consumers: node `8` (`set_size`) and node `9` (`set_to_list`). Look at `self.graph.order` at
`executor.py:50`:

```
['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10']
```

`8` runs before `9` here, but the topological sort was free to choose either — with the word ids it
picked the opposite order, which is the point. If `set_add` mutated in place, the two consumers would
see different sets depending on that choice, and the graph would have no defined answer. This is the one stop that shows *why* the design decision exists rather
than that it holds — and it is the property the `list_append` → in-place mutant attacks.

## At unit level

**Config:** `pytest: builtin_nodes only`. Fastest way into the 15 functions with no host and no
graph: put the cursor in a test and use the *Debug Test* gutter icon (enabled by
`.vscode/settings.json`). Useful for the fail-loud paths — `set_remove` on an absent item,
`list_remove_at` out of range, `set_to_list` on `{1, "a"}`.

**Config:** `pytest: collections with zero plugins`. The only way to exercise the
"needs no plugin" contract: `TestCollectionWorkflows` passes `plugins=[]`, which the CLI cannot
express because an empty `-p` means *all* installed plugins.

## Launch configs

Added to `.vscode/launch.json` for this pass (the file already held the PR #24 stage tour):

| name | what it runs |
| --- | --- |
| `coral: run a collections example (pick list/set/dict)` | `coral -p math run examples/collections/<pick>.json`, `justMyCode: false` |
| `pytest: collections with zero plugins` | `pytest tests/test_integration.py -k TestCollectionWorkflows -vv -s` |
| `pytest: builtin_nodes only` | `pytest tests/test_builtin_nodes.py -vv -s` |

The picker is a `pickString` input named `collection`. `-p math` is there only to keep startup
instant — these graphs need no plugin at all.
