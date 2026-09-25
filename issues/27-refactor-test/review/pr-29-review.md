# Review: PR #29 — the plugin conformance suites

Review of [PR #29](https://github.com/2listic/coral-python/pull/29) against
[`../plan.md`](../plan.md). Three findings are open, one blocking; [Scope](#scope) at the end
records what was examined and by what method.

## Findings

**All nine findings are closed.** [Finding 6](#6-the-executor-lost-three-test-classes) was the only
one that blocked. Recorded so the changes are not a surprise:

| # | subject | what was done |
| --- | --- | --- |
| [1](#1-the-exact-surface-test-is-a-change-detector) | `test_it_declares_the_expected_node_types`, ×3 | deleted by the author in `2516db2` |
| [2](#2-the-any-count-is-the-wrong-instrument) | `test_how_many_sockets_are_checkable`, phiflow only | deleted by the author in `2516db2` |
| [3](#3-the-graph-corpus-moves-into-the-loader) | `test_graph_corpus.py` → `graph.py:_read_id` | right call; the premises now cited in the docstring |
| [4](#4-issue-numbers-in-the-new-docstrings) | seven `issue #N` citations | removed |
| [5](#5-what-d11s-typing-actually-buys) | `print_number` / `print_text` | docstring claim corrected here; the author declined both the rename and the cast |
| [6](#6-the-executor-lost-three-test-classes) | `test_executor.py`, respecified in step 4 | three specimen shapes added, the golden regenerated, the three behaviours re-pinned |
| [7](#7-a-hand-rolled-copy-of-graph-check-4-x3) | `test_this_plugin_is_sufficient`, ×3 | deleted here — its sibling already runs the same check |
| [8](#8-the-registry-filename-the-default-that-matters-is-pinned-nowhere) | `test_the_default_filename_lands_in_the_current_directory` | the CLI's default now pinned in `test_cli.py`; the docstring repointed |
| [9](#9-two-assertions-that-cannot-see-what-they-claim) | phiflow's six-slot union and cuboid tests | strengthened here, and each confirmed to bite |

Not findings: the other nine tests in each file. `test_every_declared_function_is_callable`,
`_is_a_class`, `_is_annotated` and `test_no_function_name_collides_with_a_class_name` assert
**properties** that hold for any surface, need nothing but the plugin and `coral_core`, and are the
right inhabitants of `unit/`. String's `test_the_annotations_are_what_reject_a_swap` is the model:
it pins a fact about the plugin that nothing else in the repo pins.

## 1. The exact-surface test is a change-detector

Present in all three plugins (`math`, `string`, `phiflow`), each at line 64: an exact set comparison
against a hand-written list of that plugin's function and class names.

**Every failure of this test is an intentional change.** There is no accidental way to alter a dict
literal — you edited `get_functions()` on purpose, and a second file now tells you that you did. Its
own docstring states the intent ("should require editing this list on purpose"), which is a speed
bump, not a safety net. Compare the goldens, which fail on things you did *not* do directly: a
signature edit, an annotation change, a change in how the host renders.

**The goldens already dominate it.** Each plugin's `system/golden/node_types.<n>.json` is
byte-compared and pins the same key set *plus* arity, socket types, and the derived `Class.method`
entries — for phiflow, 13 owned keys against this test's 8.

The one argument that survives is install footprint: `system/` needs `coral-app` via the PEP 735
`test` group, so a third-party author with only `coral-core` installed sees only `unit/`. That
justifies having *some* unit-level surface check — and the four property tests listed above already
are it. This is the one member of the group that pins a *list* rather than a *property*.

It would earn its place against a **dynamically built** surface, where it would pin that the dict
does not vary by environment. Phiflow's was exactly that shape once
(`if PHIFLOW_AVAILABLE: FUNCTION_MAP.update(...)`); issue #16's D5 removed the guard. The test is a
fossil of a surface that no longer exists.

**Recommend:** delete all three. If the unit level should still say something about the surface, an
assertion that both dicts are non-empty carries the same real information at a third of the
maintenance.

**Closed:** deleted in `2516db2`, without a replacement assertion. The four property tests carry the
unit-level surface check on their own, as above.

## 2. The `Any` count is the wrong instrument

`plugins/coral-phiflow/tests/unit/test_plugin_conformance.py:138` asserts `(anys, total) == (13, 21)`
over the plugin's function annotations. Phiflow only — and never present in math or string, which
carry the stricter `test_every_function_parameter_is_annotated` instead. This count is phiflow's
substitute for that test, not a peer of it.

**Step 10 already superseded those numbers.** Item 6b recounted the slots — 23 of 48 into `TODO.md`
item 2, 32 of 120 into `CLAUDE.md`'s table, both exact — and concluded *"no test pins those
numbers."* This assertion does, and it predates the recount (`1325508`, against `e9f4b56` for the
claim), so the prose was corrected in three places while the one enforcing site was missed.

Its purpose is to stop annotation quality regressing, and to flag where the plugin can improve. It
does the first and not the second, and it charges for both:

- **It cannot point at its own subject.** The failure message is *"this plugin's annotation quality
  changed; if it improved, lower the expected count"* — no function, no parameter, no file. The one
  actionable fact (`phiflow_union` is 7 of 7) lives in the docstring, unread on a green run and
  unprinted on a red one.
- **Strict equality punishes improvement.** Fixing an annotation turns the suite red. The plan calls
  this deliberate — it "forces someone to lower the count on purpose" — but that forces bookkeeping,
  not a decision. The guard worth having is against regression, and `assert anys <= 13` gives it
  without taxing the fix.
- **Pinning `total = 21` makes it a third copy of finding 1.** Add or remove any function and it
  fails, for reasons unrelated to annotations.
- **The name overclaims.** `how_many_sockets_are_checkable` counts function slots only; a socket in
  the registry includes the five classes' constructors and methods.

**Recommend: delete it.** [`../TODO.md`](../TODO.md) item 2 records the debt in prose, which is where
"here is where this plugin can be improved" belongs, and step 10 has already moved the numbers there.
Two loose ends if you do: `test_every_function_parameter_carries_some_annotation`'s docstring points
at this test by name, and should point at `TODO.md` instead; and the regression guard goes with it,
since that sibling catches only a *bare* annotation, not a `float` decaying to `Any`.

**Second choice, if that guard is worth keeping:** `assert anys <= 13`, renamed to say *functions*,
with the offending names in the message. That keeps the floor without the bookkeeping tax — but it
also keeps two counts in circulation under one word, this test's **13 of 21** for functions against
`TODO.md`'s **23 of 48** for every port-table slot. Both are right under their own definition; say
which one the test uses.

**Closed:** deleted in `2516db2`, and the sibling docstring that pointed at it by name was repointed
in the same commit. The regression floor goes with it, deliberately — `TODO.md` item 2 now carries
the debt in prose alone, which is where the recommendation put it.

## 3. The graph corpus moves into the loader

A later layer, and not a plan step: commit `4cbead1` deletes
`tests/invariants/test_graph_corpus.py` (196 lines, 6 tests over every graph JSON on disk) and
replaces it with `_read_id` in `graph.py`, applied at parse time to node ids, edge keys and both
edge endpoints. `CLAUDE.md` is updated with it, and ~23 word ids in `test_graph.py` are renumbered.

**The right call, and stronger than what it replaced.** One rule, enforced once, at the door. It
reverses a documented position on purpose — ids were opaque so unit graphs could use
`"a"`/`"b"`/`"c"` — and the renumbering is the honest price of that. It also closes a hole the old
`_as_id` had: `key.isascii()` rejects the non-ASCII digits `isdigit()` accepts and `std::stoi` does
not.

**The premises check out**, against the two consumers that impose them: every rule holds, and each
is a conversion performed outside this repo — `std::stoi` on node and edge keys in the reference
backend, `parseInt` on endpoints and on the id counter in the editor.

**This rule is a different kind of rule from the rest of `graph.py`, and worth marking as such.**
Every other check follows from something this backend decided, or from a decision taken elsewhere
that it chose to honour. This one follows from nothing here at all: coral-python does not need
integer ids, cannot verify that anyone still requires them, and would run perfectly without the
check. It holds only because two other programs happen to convert ids to numbers. That makes the
loader a reasonable home but not the final one — the rule belongs to the *protocol*, not to any
implementation of it, and the place for it is a validator standing between the consumers, shared by
all of them and versioned with the protocol rather than with one backend.

Until that exists the docstring is the only defence, since nothing here would notice the editor
dropping `parseInt`. So `_read_id` now carries the four as a table, naming the converter rather than
a file and line, so an upstream edit cannot quietly make it wrong. **Done in this branch.**

## 4. Issue numbers in the new docstrings

Seven `issue #N` references, written in this refactor, in files `CLAUDE.md`'s rule covers: four in
`tests/invariants/test_source_rules.py`, one each in `tests/conftest.py`,
`tests/discovery/test_installed_plugins.py` and
`plugins/coral-string/tests/system/test_graphs_run.py`.

Removed, reasoning kept. The string one was mostly provenance — where the test came from and what
moved where — so it is now two lines saying what it is.

## 5. What D11's typing actually buys

Found in the editor: a `bool` reaching `print_number` prints `Print: True`, unrefused. Reproduced
directly — a `bool` primitive wired straight into `print_number` is accepted, a `str` correctly
rejected.

Both reasons are documented design and neither is new here. That edge came from `list_get`, which
returns `Any`, and the edge-type check skips whenever either side is `Any`. Even typed it would pass:
`bool` is an `int` subclass and `int` widens to `float`, both deliberate. Nothing checks types at run
time, and Python does not enforce annotations.

What it shows is that **D11's justification claims more than it delivers.** Both printers said *"an
edge feeding it is then checkable by graph check 6"*: wrong number, and typing the *target* only buys
a check when the *source* is typed as well — feed either printer from any collection extractor and it
still skips.

**Done in this branch:** both docstrings now say the check applies *only when the source is typed
too*, and name it by what it does rather than by number, since that number has already moved once —
from 6 to 8, when two checks were inserted ahead of it. The same claim in the plan's D11 row is left
as history.

**Two questions left to you, since the behaviour may be perfectly acceptable:**

1. **The names.** `math_print` / `string_print` would say what actually disambiguates these two — the
   owning plugin — and would stop promising a type they do not keep. Against it: a node type is
   platform-facing, and the platform still names `print_result` in three files, so this would be a
   second rename for it to chase. It would also touch **C0**: the three editor exports currently
   differ from genuine by exactly one field, and a second rename makes that two.
2. **The cast.** `print_number` does not act on its annotation — `print(f"Print: {value}")` prints
   whatever arrives, which is why a `bool` shows as `True` and not `1.0`. `float(value)` would make
   the declared type visible and push a genuinely non-numeric value to an error at the node that
   declared it.

Neither is the host's business; both are the plugin owner's, and doing nothing is defensible for each.

**Closed:** the plugin owner declined both. The names stay: a node type is platform-facing and the
platform still names `print_result` in three files, so a second rename would be a second thing for it
to chase, and would widen **C0** from one changed field to two. The cast stays out: no other function
in either plugin casts its inputs, `print_text` has no counterpart to it since `str()` never fails,
and a `ValueError` from inside a print node is not a better diagnostic than the edge check already
gives. The corrected docstrings are what this finding actually changed.

## 6. The executor lost three test classes

**Blocking.** Step 4's *"respecify `test_executor.py` … on the specimen"* dropped three whole classes
that `main` had, and nothing replaced them:

| class on `main` | test functions | fate |
| --- | --- | --- |
| `TestOutputPortResolution` | 2, parametrized | gone |
| `TestOutputArity` | 7 | gone |
| `TestNodeStatusMarkers` | 7 | 2 rehomed to `test_graph.py`; 5 gone |

Three behaviours are now unpinned, each confirmed by a surviving mutant:

- **The bundling rule** — whether an edge indexes into a result is decided by the port table, never
  by the value. Swap it back to `isinstance(value, tuple)` and a `-> tuple` single-output node feeding
  a sink delivers `10` where it should deliver `(10, 20)`, with the suite green. That is the
  regression issue #31 exists to prevent, and `main` pinned it by name.
- **The output-arity check** — one of only two run-time checks left in the executor. Disable both
  raise sites and nothing fails.
- **The status directory prepared on the first line of `__init__`** — move it after `Graph.from_file`
  and nothing fails, though an invalid graph then leaves the previous job's markers for the platform
  to read as this job's.

**The cause is mechanical, not carelessness.** `main`'s `executor_over` fixture patched
`build_function_map` with an *ad-hoc* map, so each test chose its own shapes. The specimen fixture
patches the name→instance lookup instead, which exposes only the fixed `SpecimenPlugin` surface — so
shapes can no longer be chosen per test, and the five functions those classes relied on had to be
ported into `specimen.py`. None were: `pair`, `triple`, `short_triple`, `long_pair` and
`not_a_tuple` are each present once on `main` and nowhere on the branch.

Two related gaps, no single-line mutant for either: **`touch_dir` is never passed to a
`WorkflowExecutor` anywhere in the suite** — the only occurrence in `tests/` is a docstring — so a
`.failed` marker is never produced *through the executor*, and `test_cli.py`'s two tests are the sole
executor-level marker coverage, over a succeeding graph.

Nothing here says the code is wrong: all three behaviours are correct, and 28 of 30 mutants died with
no over-coupling, so the suite that remains is good. It blocks because the product of this PR *is* the
test suite, the plan records no deletion of any of this, and its own line 45 lists as forbidden *"any
decision that reduces coverage of either shape."* A green run cannot show this to you.

**Recommend:** three functions in `specimen.py` — a `-> tuple` single output, an over-declaring
`Tuple[Any, Any, Any]` that returns two, an under-declaring one — recover the first two. The third
needs no specimen shape; it runs on `plugins=[]` with builtin collection nodes and an unknown type.

**Closed:** the three shapes are in `specimen.py` — `pair` (a bare `tuple` return, so one output
port), `short_triple` (declares three, returns two) and `not_a_tuple` (declares two, returns an int).
They are appended to `SpecimenPlugin.get_functions()`, so the format golden gained three entries at
the end of the specimen block with nothing moved.

`test_executor.py` regained `TestOutputPortResolution` — the three spellings of a single output,
parametrized — and `TestOutputArity` — a short tuple, the same node with a consumer wired, and a
non-tuple result. `TestStatusMarkers` is new rather than restored: it is the first place in the suite
where a `WorkflowExecutor` is handed a `touch_dir` at all, and it covers a clean run, a failing node,
and a graph rejected by validation. The marker mechanics stay where they were, on `nodestatus` itself.

Each of the three mutants this finding named was re-run against them and now dies, narrowly:
`isinstance(value, tuple)` for the bundling rule fails all three spellings; disabling both arity
raises fails all three arity tests; moving the status directory after `Graph.from_file` fails exactly
the validation-failure test. Nothing else moved in any of the three runs.

## 7. A hand-rolled copy of graph check 4, ×3

Math's and phiflow's `test_this_plugin_is_sufficient`, and coral-app's
`test_the_host_needs_no_plugin_for_them`. Each re-reads the graph JSON and asserts
`node["type"] in port_table` for every node — which is `_check_node_types_are_known` transcribed.
`test_graph_constructs`, three lines above in the same class, calls `Graph.from_file` over the same
parametrisation with the same `port_table` fixture, so it runs that check already. No graph could
fail one and pass the other.

Same shape as finding 1, and the claim it documents — "the owning directory *is* the answer" — is
already in each module docstring, where it costs nothing.

**Closed:** deleted here, 9 cases in total, one per shipped graph. `ruff` then dropped the
`import json` each file kept only for it.

## 8. The registry filename: the default that matters is pinned nowhere

`coral-app/tests/test_registry.py:459`. Two defaults exist —
`save_registry_to_file(filename="registry-py.json")` is the library's, and `node_types.json` is the
CLI's, *"the fixed filename the DealiiX platform probes for"*. `cli.py` always passes `args.output`,
so the library default is unreachable from any `coral` command.

The test asserts `registry-py.json`. Its docstring is about the other one: *"`coral register` must
write where the caller stands."* Nothing pins that — both places in the suite naming
`node_types.json` pass it explicitly, and `test_cli.py` has no `register` case at all.

Pre-existing, not introduced here; `main` is the same. What is new is noticing that the docstring
promises a guard that does not exist.

**Recommend:** not deletion — write the test the docstring describes: drive `main()` with
`["coral", "register"]` and assert `node_types.json` appears in the cwd. Left to you, since it is a
new test and where the platform's contract gets pinned is a decision rather than a tidy-up.

**Closed:** written as recommended. `test_cli.py` gained `TestRegisterOutput`, driving `main()` with
`["coral", "register"]` and asserting `node_types.json` appears in the cwd, plus a case for `--output`
redirecting it. Mutating `DEFAULT_REGISTRY_FILENAME` to the library's string fails exactly that first
test and nothing else. The assertion on `registry-py.json` is kept — it is a real default for a direct
caller of `save_registry_to_file` — and its docstring now says so, instead of promising the CLI's
contract it never tested.

## 9. Two assertions that cannot see what they claim

Both in phiflow's new unit tests, both one line from being real.

`test_the_full_six_slots_are_usable` promised *"all six are combined — the documented maximum,
asserted so it stays true"* and asserted `is not None`. A regression dropping slots 3–6 returns a
union of the first two, which is not `None`. Its own sibling three lines up shows the way: the
function prints `phiflow_union: combined N geometries`.

`test_a_cuboid_holds_a_phiflow_cuboid` called the four-scalar-to-two-`vec` conversion "the
interesting part" and asserted only `is not None`, where its box and sphere siblings assert
`isinstance`. Swapping centre and half-size passed.

Step 5 traded four simulation tests away on the strength of these new unit tests being *"a net gain
rather than a trade"*, so a replacement that cannot see the regression weakens that trade.

**Closed:** both strengthened here, and each confirmed to bite by mutating the source it guards —
dropping the later slots fails the union test, reading half-size as the centre fails the cuboid
test, one test each and nothing else.

## Scope

- `plan.md` in full, execution record included.
- `test_plugin_conformance.py` ×3, phiflow's source and golden, `pytest.ini`, and the plugin
  self-guard (`conftest.py` / `<name>_suite.py` / `test_plugin_present.py`).
- `graph.py`, `test_graph.py` and the seven cited docstrings, for findings 3 and 4.
- **D10** — `errors.py`, both raise sites, `build_port_table`'s `put()` — read and mutation-tested.
- **Mutation pass, 37 mutants** across `nodestatus.py`, `executor.py`, `graph.py`, `registry.py`,
  `nodeports.py` and `builtin_nodes.py`, picked from the decisions `CLAUDE.md` documents. **34
  killed, 3 survivors** — all three from one cause, [finding 6](#6-the-executor-lost-three-test-classes).
  No over-coupling: the one mutant that failed more than six tests was reversing parameter order,
  which legitimately breaks every executing graph.
- **C0**, checked rather than taken: each of the three edited exports differs from its pre-PR
  version by exactly one line, `"print_result"` → `"print_number"`. No node, edge or position moved.
- **D11** end to end: both plugin sources, and all four goldens diffed against `main`. The platform's
  contract moves in exactly two places — math's and string's printer entry, each a key rename plus a
  socket going from `any` to `float` / `str`. Phiflow's golden is byte-identical, and
  `node_types.all.json`'s deletion with `node_types.format.json`'s arrival is **R1** as designed.
  Nothing unaccounted for.
- Run: 507 passed / 4 deselected, `ruff` clean; the surface lists against plugin
  source; phiflow's golden at 13 owned keys; GWT adherence 447/448, none missing, so **O2** held;
  no graph wires `test_tuple_return`.
- **Consumer pass in the DealiiX editor.** A registry generated from this branch loads; a graph
  exported from the editor still runs through the now-stricter `_read_id`; `list_new` renders and
  wires as the first zero-input *function* node; and the 22 sockets typed `list`/`set`/`dict` —
  socket types with no registry key of their own — render and validate. One surprise, which turned
  out to be documented design: [finding 5](#5-what-d11s-typing-actually-buys).
- **Every new test module read**, for the class mutation is blind to: redundancy and tautology,
  which is what findings 1 and 2 were. Yielded findings 7, 8 and 9; **twelve modules came back
  clean**, and there are no category violations anywhere. Four lower-value items were left unraised.
  `test_graph.py` and `test_nodeports.py`, reworked here, were reviewed by test inventory rather
  than assertion by assertion.
