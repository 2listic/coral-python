# Review: PR #29 — the plugin conformance suites

Review of [PR #29](https://github.com/2listic/coral-python/pull/29) against
[`../plan.md`](../plan.md). Partial: read as far as
[The separation principle](../plan.md), so the plan's rationale is covered and its execution detail
is not.

## Findings

**Yours to decide:**

| # | subject | verdict |
| --- | --- | --- |
| [1](#1-the-exact-surface-test-is-a-change-detector) | `test_it_declares_the_expected_node_types`, ×3 | redundant with the goldens — recommend deleting |
| [2](#2-the-any-count-is-the-wrong-instrument) | `test_how_many_sockets_are_checkable`, phiflow only | pins totals step 10 superseded — recommend deleting, or loosening to an inequality |

**Already settled, and fixed in this branch** — recorded so the change is not a surprise:

| # | subject | what was done |
| --- | --- | --- |
| [3](#3-the-graph-corpus-moves-into-the-loader) | `test_graph_corpus.py` → `graph.py:_read_id` | right call; the premises now cited in the docstring |
| [4](#4-issue-numbers-in-the-new-docstrings) | seven `issue #N` citations | removed |

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
