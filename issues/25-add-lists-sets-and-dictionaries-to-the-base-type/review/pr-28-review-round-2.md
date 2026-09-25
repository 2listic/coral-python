# Review: PR #28, round 2

The code review. Round 1 — [`pr-28-review.md`](pr-28-review.md) — returned the review request on one
blocking finding without reading the code; this file is kept separate so that document stays still.
The pass it executes is [`pr-28-review-plan.md`](pr-28-review-plan.md).

Status: **steps 1–4 done**; step 5 (the guidelines doc) is the remainder. Findings are numbered
continuing from round 1, where finding 1 was the non-numeric node ids.

| section | plan step | state |
| --- | --- | --- |
| [1. Round 1's finding 1](#1-round-1s-finding-1--resolved-in-622c94b) | — | **resolved**, verified |
| [2. Design review](#2-design-review--the-assumptions-and-choices) | 2 | done — **finding 3** in §2.2 |
| [3. Implementation review](#3-implementation-review--plan-versus-code) | 3 | done — every claim recomputed, all hold |
| [4. Tests under mutation](#4-tests-under-mutation) | 4 | done — 13 mutants, 12 killed, 1 survived |
| [5. Raised separately](#5-raised-separately--tracked-as-issues-not-pr-28-feedback) | — | 3 items, all filed as issues |
| [6. A common thread](#6-a-common-thread) | — | a shape shared by §2.1 and §5.1, not a finding |

Step 1 of the plan produced no findings of its own beyond finding 2 (§5.1); its output is
[`debug-walkthrough.md`](debug-walkthrough.md) plus three launch configs.

## 1. Round 1's finding 1 — resolved in `622c94b`

The author renumbered all seven graph files, and went further than the review asked: edge keys were
renamed too, and `tests/test_graph_ids.py` now guards the rule. Checked independently rather than
taken on trust:

| check | result |
| --- | --- |
| the seven files renumbered | ids `0…n-1`, edge keys `0…m-1`, declaration order preserved |
| every graph file in the **whole repo**, not only the two directories the guard searches | 14 found, 0 offenders on ids, edge keys or endpoints |
| endpoints written as JSON numbers, "as all ten pre-existing graphs do" | holds — all 14 files use `int` endpoints |
| the three examples still byte-identical to their fixtures | identical |
| the new `name → id` maps in `test_integration.py` | correct — derived positionally from the pre-commit files: contiguous ids, types preserved, all four maps match |
| suite | 317 passed, 3 deselected (slow) = 320 collected, as claimed |
| all three examples through the CLI | run, correct values |
| the round trip through the editor — step 8's one open item | confirmed by pcolt: `set.json` loads, runs and returns the expected results |

`tests/test_graph_ids.py` is solid: it rejects leading zeros and negatives (`std::stoi("01")` is `1`,
so `"01"` and `"1"` would name one node), catches two ids denoting the same integer, discovers files
from disk, and carries a non-vacuity test so an empty discovery cannot pass green.

### 1.1 Two imprecisions in the fix's own notes

Neither is a defect and neither needs an edit. Both are worth knowing.

1. `tests/README.md`'s file tree lists the other 13 test files but not `test_graph_ids.py` — worth a
   line next time that tree is touched, since PR #28 itself added five missing entries to it
   ([`plan.md` step 7's deviation](../plan.md)).
2. [`plan.md`'s new step 8](../plan.md) rejects a `name` field because it "invents a key the editor would
   drop on re-export". The field is in fact part of the protocol — `LeanStandardNode` declares
   `name?: string`, `UnifiedNode.svelte:186-193` renders it as the node's headline with the type
   beneath, `EditNodeNameModal.svelte` sets it, the exporter preserves it (`if (data.name) node.name =
   data.name`), and the C++ backend reads it (`coral_network_implementation.h:612`) and prints it
   beside the id. That evidence only landed in [#32](https://github.com/2listic/coral-python/issues/32)
   after `622c94b`, so it was not available at the time. The renumbering is right either way; see
   §5.3.

## 2. Design review — the assumptions and choices

The plan's step 2, one subsection per question: what was decided, what it costs, and what is still
unverified. Numbering matches the plan's items 2.1–2.6.

### 2.1 Design decision 3 — `list`/`set`/`dict` as socket type names, not node types

Where it comes from: row 3 of the decisions table in [`plan.md`](../plan.md#decisions), argued in full in
[`plan.md` → *Decision 3 in full*](../plan.md#decision-3-in-full), which weighs three options — (i) keep
both a `list` primitive node and `list_new`, (ii) drop `list_new` and let the primitive create,
(iii) type names only, chosen. It is implemented by [step
1](../plan.md#1-the-three-type-names--packagescoral-appsrccoral_appprimitivespy) and nothing else, and it
is what stop 3 of [`debug-walkthrough.md`](debug-walkthrough.md) shows.

**Verdict: right call, better justified than most of the plan.** Its two open bets are closed and its
central claim holds. What is left concerns future code, not this PR.

- **Enforced, not merely intended.** `Graph({'0': {'type': 'list'}}, {}, ports)` raises
  `ValueError: Node '0' has unknown type 'list'`. Under option (i) or (ii) that node would have been
  legal, so "one way to build a collection" is a property of the code, not of the prose.
- **Bet 2, zero-input function nodes** ([`plan.md:66-67`](../plan.md)) — `set.json` loads and runs in the
  editor.
- **Bet 1, `"list"` as a socket type with no `registry[...]` key** ([`plan.md:61-65`](../plan.md)) — safe
  by construction. A socket type string is used in exactly two places in the platform: an equality
  test in edge validation (`graphParser.ts:270-271`) and a text label (`UnifiedNode.svelte:263`,
  `:275`). Every `getNodeData(...)` call passes a **node's** type, never a socket's, so nothing looks a
  socket type up.
- **Where the value lands:** the annotations are bare classes, so check 6 can accept `list → list` and
  reject `list → set`. That is the whole return on step 1.

Three latent consequences the decision note does not mention:

1. **The reverse map is silent on collisions.** `_TYPE_NAME_OF` is
   `{v: k for k, v in TYPE_NAMES.items()}`, so a name is dropped if two names ever map to one type —
   add `"array": list` and `"list"` disappears with no error.
2. **`List[int] → "any"` costs nothing *today*, and that is luck.** No plugin annotates a node
   signature with a generic (the `Dict[str, Any]` hits are `get_functions`/`get_classes`, not node
   types). The first author who writes `-> List[float]` gets an `"any"` socket and loses check 6 on
   that edge. The deviation at [`plan.md:125-129`](../plan.md) records the behaviour but not this cost.
3. **The editor's edge check is stricter than coral-python's** — which turned out not to be latent at
   all. Promoted to §2.2.

### 2.2 Finding 3 — the interop fixture cannot be loaded in the editor

`tests/fixtures/valid_workflows/network-collections-math.json` is the fixture design decision 2 was argued on:
a collection feeding a plugin function. Loading it in the editor drops two edges:

```
Edge id: 8 - Type mismatch - source output type 'any' does not match target input 'float'
Edge id: 9 - Type mismatch - source output type 'any' does not match target input 'float'
```

Both carry a value out of the list (`list_get`, return `Any`) into `add(a: float, b: float)`. The
editor's rule (`graphParser.ts:268-273`, and the same rule for interactive wiring in
`connectionsValidation.ts:60-84`) treats `"any"` as a wildcard **only on the target side**, so an
unknown source cannot feed a typed port. coral-python's check 6 skips when *either* side is `Any`.

Rejected edges are not merely flagged: `importGraphFromProtocol` loads only `validEdges`, so the wires
never reach the canvas and saving the graph back makes the loss permanent.

**Scope, measured.** Applying the editor's rule to all 14 graphs the repo ships, exactly one is
rejected — this fixture. The other 13 pass because their `Any` outputs happen to feed `Any` inputs. So
**PR #28 is the first change to ship a graph the editor cannot load**, and it is the same class as
finding 1: an artefact verified through the CLI, the one consumer that does not care.

Comparing the two rules over all 81 pairs of the nine socket type names gives 11 disagreements, all
the same direction: 8 × `any → <typed>`, plus `int → float`, `bool → int`, `bool → float` — so numeric
widening is a second live case, and a `list_size` output cannot be wired into a `float` parameter
either.

Not fixable by better annotations: `list_get` cannot know its element type. The fix is in the other two
repos, and the order matters, so both are filed with that noted —
[dealiiX-platform#215](https://github.com/2listic/dealiiX-platform/issues/215) for the rule and the
edge-dropping, [#34](https://github.com/2listic/coral-python/issues/34) for the mirror-image gap
(coral-python renders a class annotation as `"any"`, so the editor cannot check class wiring at all;
relaxing the platform rule first would make that worse).

**What this PR owes:** nothing in the code. The fixture is correct for the Python suite. But the claim
that the collection work was verified end to end does not hold for the editor, and whoever documents
the interop case should say that it currently needs a platform fix to be drawable at all.

### 2.3 Purity — the guarantee is shallow, and the cost is memory, not time

The decision (`plan.md`'s "Semantics common to all of them") is right: a node's result is read by every
downstream consumer in an order the topological sort chooses, so in-place mutation would make the
outcome depend on that choice. Three things about it are worth stating precisely.

**Nothing enforces it.** `executor.py:65` passes references and stores whatever comes back —
`arguments[0] is results[<source>]`, no copy anywhere. Purity lives entirely in the 15 functions, by
two techniques: build a new container (`[*lst, item]`, `s | {item}`, `{**d, key: value}`,
`sorted(s)`) or copy then mutate the copy (`out = list(lst); del out[index]`). A plugin function that
mutated its argument would corrupt the upstream node's stored result for every other consumer, and no
check anywhere would notice. That is why step 4's purity mutants matter more than they look: the DAG's
correctness rests on 15 one-line implementations, not on an invariant.

**The guarantee is shallow, and that is not written down.** `[*lst, item]` copies the outer list; the
elements are the same objects, and `list_get` hands one straight back by reference:

```
element is shared : True
outer2 now        : [[1, 2, 999]]   <- mutated through the element a consumer received
```

So a node that receives a mutable element and changes it in place changes it inside every collection
holding it, and inside `results`. Harmless for today's fixtures — ints, floats and strings are
immutable — and it stops being harmless the moment a graph puts a plugin object into a list, which is
exactly what design decision 2's interop case invites. `builtin_nodes.py`'s "returns a *new* collection and
never touches its input" is accurate, but reads as a stronger promise than it is.

**Copying costs nothing worth worrying about.** Measured out of curiosity, since `plan.md` flags an
O(n²): building a 4000-element list takes 75 ms and 69 MB, and it needs 4000 append *nodes* to get
there, so no drawable graph reaches it. Closed, not a concern.

### 2.4 `set_to_list` sorts, which adds a failure the operation does not need

Elements are `Any`, so a set holding an `int` and a `str` is legal wiring. The graph validates, then
fails while running: `TypeError: '<' not supported between instances of 'str' and 'int'`.

`list_get`'s `IndexError` and `dict_get`'s `KeyError` depend on the user's data and cannot be known at
t=0 — inherent, and the fail-loud contract covers them. This one is created by the choice to sort;
`list(s)` never raises. The trade is deliberate and documented (a set of strings iterates differently
between runs, which would make a graph non-reproducible), and reproducibility is worth buying — it is
just the one run-time failure the builtins introduce rather than inherit.

### 2.5 The shape of the solution, against the rest of the system

**What the code can do.** The 15 ops are create / add / extract / inspect / remove — no iteration, map,
fold, contains, concatenation or slicing. So a collection is a counter and an indexed box, and every
element leaves through `list_get` / `dict_get` at a literal index or key. Checked across all three
plugins: **no plugin port is typed `list`, `set` or `dict` — zero inputs, zero outputs.** Nothing
outside the 15 builtins can receive a collection; a plugin only ever sees elements, one at a time,
through an `Any` socket.

**What the C++ backend does instead.** A collection there is an *elementary type* — registered next to
`int`, `double` and `std::string` via `register_elementary_type<std::set<unsigned int>>()` — so it is a
**primitive node carrying a literal** (`coral/test_files/SetSum.json`):

```json
"0": {"type": "std::set<unsigned int>", "value": "[1, 2, 3, 4, 5]"},
"1": {"type": "sum_set"}
```

One node instead of a chain, the element type is part of the node type, and a plugin function consumes
the collection whole (`sum_set(const std::set<unsigned int> &)`). No collection *operations* are
registered anywhere in that codebase.

**Three consequences worth acting on.**

1. **The two backends' collection surfaces do not overlap.** A graph built from `set_new`/`set_add`
   cannot run on the C++ backend; a graph with a `std::set<unsigned int>` node cannot run here. For a
   feature framed as adding collections to the *base types*, parity deserves an explicit decision
   rather than falling out of two independent designs.
2. **A premise behind design decision 3 does not hold.** [`plan.md`](../plan.md#decisions) rules out a
   collection primitive because it "could only ever be empty (JSON cannot express a literal set or
   dict)". `SetSum.json` shows otherwise: the literal travels as the string `"[1, 2, 3, 4, 5]"` and the
   declared type parses it — exactly how coral-python already treats `"5"` for an `int`. The option
   table considered an *empty* collection primitive and correctly rejected it; a *literal* one was
   never on the table.
3. **Neither model is sufficient alone, and they are complementary.** The literal form gives one node,
   element typing the editor can actually check, and direct consumption by plugins — but cannot build a
   collection from *computed* values, which is precisely what the four fixtures do. The ops give that
   and nothing else.

**Verdict on the code as produced: sound, and it does the thing the C++ model cannot.** The two gaps
are about reach, not correctness — no literal form, and no plugin that can accept a collection. Both
are follow-up work rather than PR feedback.

On functions versus wrapper classes: the author's reason was that functions were simpler, which is
true and sufficient. It also happens to be the better-typed choice — a wrapper's instance port would
render `"any"` in the registry ([#34](https://github.com/2listic/coral-python/issues/34)), whereas a
bare `list` renders `"list"`. The interop argument recorded in design decision 2 is not what carries
it, since no plugin accepts a collection either way today.

Against [`desiderata.md`](../desiderata.md) — "some method to add some element … and also some method to
extract elements" — the feature satisfies the letter.

### 2.6 Three smaller ones

- **A plugin shadowing a builtin is dropped in silence.** `function_map.update(BUILTIN_FUNCTIONS)` runs
  last, so the plugin's entry disappears with no warning.
  `test_plugin_discovery.py::TestBuiltinsAreNotShadowable` pins the precedence, which is the part that
  matters, and [`plan.md:205`](../plan.md) already records failing loud as a separate change. One log line
  at merge time would close it.
- **`-1` means two things in one file format.** `list_get([10, 20, 30], -1)` is `30` — Python indexing,
  pinned by a test — while `"source_output": -1` means "the only output". Same literal, same JSON, two
  conventions. No bug; a hazard for whoever writes the editor's tooltip.
- **The three examples are byte copies of three fixtures**, with nothing checking they stay in step
  ([`plan.md:345-348`](../plan.md) accepts this). Verified in sync today, including after `622c94b`
  renumbered all seven.

## 3. Implementation review — plan versus code

Every countable claim was recomputed rather than read. **All of them hold.**

| claim | verdict | how |
| --- | --- | --- |
| `PRIMITIVES_MAP` unchanged; `executor.py` / `graph.py` / `nodeports.py` untouched | holds | git diff vs `origin/main`: only additions after `PRIMITIVES_MAP`, and no source file of those three in the diff (only `tests/test_graph.py`) |
| the 15 ops match the plan's table | holds | signature and body compared for all 15 against the table, programmatically — no difference |
| goldens: 15 keys added, 0 removed, 0 changed, added set is exactly `BUILTIN_FUNCTIONS` | holds | `node_types.all.json` vs `origin/main` (the only golden with a "before"); all four contain all 15 builtins, 6 primitives, and no `list`/`set`/`dict` entry |
| `node_types.all.json` constructor order is `sorted(discover())` | holds | `Calculator`, PhiFlow ×5, `StringProcessor` = math, phiflow, string |
| `CLAUDE.md`'s annotation-slot table (28/1/27, 8/1/7, 48/23/25, 36/9/27 → 120 slots, 34 `Any`, 86 checkable) | holds, every number | recomputed from the installed surface under the table's own definition of a slot |
| step 5's graph cases exist | holds | 6 compatibility tests plus `test_a_collection_is_not_a_node_type` |
| step 6's fixtures assert values, not shapes | holds | e.g. `results[LIST_NODES["without_first"]] == [2, 3]`, `size == 3`, `with_duplicate == {5, 7}` |
| the suite passes with no plugin installed | holds | uninstalled all three: **239 passed, 79 skipped, 0 failed** (2.4 s). The plan's 187/78 was true when written; the delta is tests added since |
| `test_acceptance.py`'s stale-wheel fix | present | `--refresh-package` per local package, with the mechanism written down at `:85-96`. The historical bug itself was not re-created |
| `TYPE_NAMES` / `COLLECTION_TYPES` have exactly one consumer | holds | only `registry.py`'s reverse map reads them; `primitives.py` says so itself |
| `TODO.md`'s "tautological tests" list | accurate where sampled | `test_obstacle_workflow_execution` asserts `len(results) > 0` and `isinstance(results, dict)`; `test_registry_file_is_valid_json` the same shape |

Two things worth flagging, neither a defect in this PR.

**The falsified premise is now in the code, not just the plan.** `primitives.py`'s comment above
`COLLECTION_TYPES` repeats it: "JSON cannot express a literal set or dict, so such a node could only
ever produce an empty collection". §2.5 shows the C++ backend doing exactly that
(`"value": "[1, 2, 3, 4, 5]"`, parsed by the declared type). The next person deciding whether a literal
collection primitive is possible will read that comment and stop. One line to fix, and worth fixing
because it forecloses an option that is actually open.

**`Any → collection` is tested as deliberate, and its consequence is not written down.**
`test_any_into_a_collection_skips_the_check` pins the skip, so the laundering below is intended
behaviour, not an oversight — but with an `Any` in the middle a list reaches every *set* operation and
most succeed by duck typing:

```
list_new -> list_append(outer, inner) -> list_get(0) -> set_size
check 6: accepted (the Any edge skips)
run time: set_size(a list) = 0    -- no error, wrong operation, plausible answer
```

`set_remove` on a list would even return a set. Nothing fails at validation or at run time. The skip
rule predates this PR; what the collections add is a supply of `Any`-returning nodes that makes it
reachable in ordinary graphs.

## 4. Tests under mutation

Method from PR #24's review: pick mutants from the design decisions rather than mechanically, change
one line, run the suite, revert. Here it was scripted — 13 mutants, each run against
`pytest -m "not slow and not phiflow"` (~1 s, 318 tests), with `git checkout` after each and
`git diff --quiet` asserted at the end.

**12 killed, 1 survived.**

| mutant | verdict |
| --- | --- |
| `list_append` mutates in place (`lst.append`) | killed |
| `set_add` mutates in place | killed |
| `dict_set` mutates in place | killed |
| `set_to_list` returns `list(s)` instead of `sorted(s)` | killed |
| `set_remove` uses `discard` | killed |
| `list_remove_at` slices instead of `del` | killed |
| `list_get` returns `None` out of range | killed |
| `list_size` off by one | killed |
| `BUILTIN_FUNCTIONS` applied *before* the plugins | killed |
| `TYPE_NAMES` drops the collections | killed |
| two `BUILTIN_FUNCTIONS` keys reordered | killed |
| `executor.py:101`: drop the `isinstance(value, tuple)` clause | killed |
| `executor.py:101`: drop the `< len(value)` bound | **survived** |

**The suite is stronger than I expected in the one place I predicted a gap.** The plan's table guessed
`set_to_list → list(s)` would survive as an equivalent mutant, on the grounds that fixtures use small
integer sets where iteration order already equals sorted order. It dies instead, to
`TestSetToListDeterminism::test_string_elements_are_ordered_by_value_not_by_hash`
(`['apple', 'pear', 'fig']` vs `['apple', 'fig', 'pear']`) and
`test_incomparable_elements_raise`. Choosing string elements there was the right call and it is what
makes the assertion bite.

**The survivor is the one already known.** Dropping the `< len(value)` bound changes an out-of-range
`source_output` from "silently pass the whole tuple" to `IndexError` — arguably the better behaviour —
and the suite cannot tell the two apart. So that guard is unpinned in *either* direction, which
strengthens [#31](https://github.com/2listic/coral-python/issues/31): whoever fixes it can choose the
semantics freely, because no test currently expresses a preference.

Nothing else to report: every property this PR's design leans on — purity for all three containers,
fail-loud on absent index/key/item, sortedness, builtin precedence, socket typing end to end, and the
goldens' byte order — is pinned by at least one assertion that fails when the property is removed.

## 5. Raised separately — tracked as issues, not PR #28 feedback

**Nothing in this section blocks PR #28, and none of it is this PR's code.** All three were found
while reviewing it, all three are tracked in their own issue, and they are summarised here only so the
review is a complete account of what the pass turned up. The issues hold the detail.

| | what | where it lives | whose code |
| --- | --- | --- | --- |
| §5.1 Finding 2 | `source_output` silently unwraps a tuple from a single-output node | [#31](https://github.com/2listic/coral-python/issues/31) | PR #24 (`executor.py`, merged `466b299`) |
| §5.2 Suggestion A | one helper for the three copies of the same comprehension in `nodeports.py` | [#33](https://github.com/2listic/coral-python/issues/33) | PR #24 (`nodeports.py`) |
| §5.3 Suggestion B | put the readable node names in the protocol's `name` field | [#32](https://github.com/2listic/coral-python/issues/32) | new work, follows from finding 1 |

### 5.1 Finding 2 — `source_output` unwraps a single-output tuple → [#31](https://github.com/2listic/coral-python/issues/31)

Found while stepping through `_input_values` for step 1 of the plan.
[`executor.py:100-102`](../../../packages/coral-app/src/coral_app/executor.py#L100-L102) decides whether a
value is a bundle of outputs from its runtime type (`isinstance(value, tuple)`), when the port table
already knows. Two consequences, both silent:

```
pair() -> tuple  returning (10, 20)   — ONE output port, three legal spellings of "the only output"
  source_output omitted -> (10, 20)     <- correct, and the spelling real graphs never use
  source_output = 0     -> 10
  source_output = -1    -> 20

triple() -> Tuple[Any, Any, Any]  returning (10, 20)
  source_output = 2     -> (10, 20)     <- out of range, no IndexError, whole bundle passed
```

The fix direction, the reproduction and the two open decisions are in the issue. No test covers any of
it, so both mutants go into §4's table.

### 5.2 Suggestion A — one helper in `nodeports.py` → [#33](https://github.com/2listic/coral-python/issues/33)

Readability only, no behaviour change. `nodeports.py` writes the same "parameter → (name, annotation)"
comprehension three times, in three shapes, and each one unpacks a pair whose first half is already
inside the second (`param.name` is the same string as `name`). One `_input_ports(params)` helper
replaces all three and leaves each call site holding only its own special part — the C-extension
fallback in `_constructor_ports`, the instance-at-port-0 convention in `_method_ports`. Both versions
were run over every callable node type: 30 compared, 0 differences.

### 5.3 Suggestion B — readable names belong in `name` → [#32](https://github.com/2listic/coral-python/issues/32)

The constructive half of finding 1: node ids must be integers, so the word ids (`empty`, `with_five`)
need a home, and the protocol already has one. A node's optional `name` is rendered by the editor
(`UnifiedNode.svelte:186-193` shows id + name + type) and read and logged by the C++ backend
(`coral_network_implementation.h:612`, then printed alongside the id in `execute_node_task`).
coral-python ignores it entirely.

```json
"1": {"type": "set_new", "name": "empty"},
"2": {"type": "set_add", "name": "with_five"}
```

Legible in the file, legible on the canvas, valid for both backends. Ids address, names describe —
which is also why `name` cannot replace an id: nothing anywhere enforces its uniqueness.

## 6. A common thread

Not a finding, and deliberately not an issue yet — a shape that keeps recurring, worth naming once so
the separate items above are not mistaken for one repeated one. **Information that one stage already
knows is not carried to the stage that needs it, so the later stage re-guesses or re-invents it.**

| instance | who knows | who re-guesses |
| --- | --- | --- |
| §5.1 | the port table knows a node's output count | `_input_values` asks the runtime value: `isinstance(value, tuple)` |
| §2.1(2) | the annotation knows the element type | the registry collapses it to `"any"`, and both wiring checks then skip |
| §2.1(3) | `graph.py` check 6 decides compatibility with `issubclass` | the editor decides it again by string equality, and the two disagree |
| §2.1(1) | `TYPE_NAMES` maps name → type | the reverse direction is derived on the fly, silently lossy if two names share a type |

PR #24's review found the same shape as its finding 3 (the executor calling `inspect.signature` on a
callable whose arity the port table had already recorded), so this predates the collection work.

Whether it deserves an issue of its own depends on steps 3 and 4: if they turn up more sites, one
bounded audit is worth filing; if they do not, four scattered instances are better left as review
notes than as an open ticket nobody can close.
