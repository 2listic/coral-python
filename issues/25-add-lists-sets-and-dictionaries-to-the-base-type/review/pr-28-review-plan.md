# Plan: deep review of PR #28

[`pr-28-review.md`](pr-28-review.md) returned the review request on one blocking finding and read no
code. This plan is the pass that reads it: the implementation against [`plan.md`](../plan.md), the
decisions that shaped it, the tests under mutation, and the debugger instrumentation that makes all
three checkable by hand rather than by assertion.

**Inputs.** [`desiderata.md`](../desiderata.md) (requirements), [`plan.md`](../plan.md) (7 steps, 7
decisions, 24 deviations), [`TODO.md`](../TODO.md) (a parked test audit),
[`../23-refactor-executor/pr-24-review.md`](../../23-refactor-executor/pr-24-review.md) (method).

**Outputs.**

| artifact | what it is |
| --- | --- |
| `pr-28-review-round-2.md` (new, this folder) | this pass's findings — kept separate from the returned review, so that document stays still |
| `debug-walkthrough.md` (new, this folder) | breakpoint-by-breakpoint tour of the added logic |
| `.vscode/launch.json`, extended | run configs for the collection graphs — **gitignored**, so the doc above is the durable half |
| `docs/reviewing-generated-prs.md` | the review method, written down (step 5) |

## Ground rules

Carried from PR #24's review, and they apply harder here because `plan.md` is longer than the code
it describes:

1. **`plan.md`, `TODO.md` and the docstrings are the artifact under review, not evidence about it.**
   Every deviation note is a claim about what was done. Checkboxes are claims. The 24 deviations are
   the most valuable part of the document *and* the least verified.
2. **Every counted claim gets recomputed** — the annotation-slot table (86/120, 34 `Any`, rows
   28/8/48/36), "15 keys added, 0 removed, 0 changed", "187 passed / 78 skipped", TODO.md's "246 test
   functions". `plan.md:377-382` already records one slot table whose rows did not sum to its prose.
3. **Read by executing.** A finding that came from running something outranks one that came from
   reading. Hence step 1 first.
4. **Prose defending a mechanism is a reason to check the mechanism.** `builtin_nodes.py` is 177
   lines for 15 one-line functions; most of it is justification.

## Step 1 — instrument for the debugger

Goal: every logic this PR adds can be stopped inside from a menu, with no file editing. The existing
`launch.json` covers the stage tour and pytest; nothing there exercises a builtin.

- [x] Add run configs: a picker over the three `examples/collections/*.json`; the zero-plugin case via
      `pytest -k TestCollectionWorkflows` (which already passes `plugins=[]`, so no driver script was
      needed); `pytest tests/test_builtin_nodes.py` for unit level.
- [x] Write `debug-walkthrough.md`: one section per stage, each naming a file:line to break on, what
      to inspect there, and the question it answers.

| break at | inspect | the question |
| --- | --- | --- |
| `__init__.py`, after the plugin loop | `function_map` before vs after `update(BUILTIN_FUNCTIONS)` | design decision 7 — is the builtin really applied last? |
| `nodeports.build_port_table` | the `NodePorts` for `list_new` and `list_append` | zero inputs; `("lst", list)` typed, `("item", Any)` not |
| `registry.python_type_to_string` | `_TYPE_NAME_OF` | why `list` renders `"list"` but `List[int]` renders `"any"` |
| `graph._check_edge_types` | the `list → list` and `Any → list` pairs | which collection edges are actually checked, and which skip |
| `executor.execute`, the `set_add` node | `results` before and after | purity: the input set object is untouched |
| same, a fan-out node | the two consumers of one list | the reason purity matters, seen once |

- [x] Verify each breakpoint actually stops with the config as written — a walkthrough nobody ran is
      another unverified document. Done with `coverage`, per target line.

Output: `debug-walkthrough.md`, extended `launch.json`, and finding 2 in the round-2 file.

## Step 2 — the assumptions and choices

Goal: name the decisions that shaped the result, separate the ones that were taken deliberately from
the ones that fell out, and say which are still open. Each gets a reproduction or a measurement, not
an opinion.

Numbered to match the round-2 file's subsections, so a reader can go from a question here to its
verdict there.

- [x] **2.1 — Design decision 3** (`plan.md:28-77`): is it enforced rather than merely intended, and
      are its two platform bets (`plan.md:59-70`, recorded unconfirmed at `:287-289`) answerable?
- [x] **2.2 — The editor's edge check versus check 6.** Do the two validators agree about which graphs
      are valid? Became finding 3.
- [x] **2.3 — Purity**: what it guarantees, and what the copying costs.
- [x] **2.4 — `set_to_list`'s `TypeError`.** Reachable from a valid graph, since elements are `Any`.
      Unlike `IndexError` / `KeyError` it is not inherent in the operation — sorting creates it. Is the
      trade worth stating?
- [x] **2.5 — Is this the right shape, judged against the rest of the system?** What a graph can do
      with a collection; whether any plugin port can receive one; how the C++ backend models
      collections and whether the two surfaces are compatible; and whether wrapper classes or a literal
      primitive would have been better.
- [x] **2.6 — Three smaller ones.** Design decision 7's silence (a plugin declaring `list_append` is
      ignored with no warning; `plan.md:205` defers failing loud); the `-1` overload
      (`plan.md:181-185`, "from the end" on an index port versus "the only output" on a
      `source_output`); and the examples being byte copies of fixtures with nothing checking they match
      (`plan.md:345-348`).

Output: one subsection per item in the round-2 file — what was decided, what it costs, what is still
unverified.

## Step 3 — plan versus implementation

Goal: does the code do what `plan.md` says, and do the deviations describe their own effects
correctly? Per step, and scripted wherever the claim is countable.

- [x] **Step 1 (types).** `PRIMITIVES_MAP` byte-identical to before (git); `COLLECTION_TYPES` /
      `TYPE_NAMES` shape; `_TYPE_NAME_OF` fed from `TYPE_NAMES`; `generate_registry`'s `primitives`
      argument still `PRIMITIVES_MAP` keys. Confirm `executor.py` / `graph.py` / `nodeports.py` are
      untouched (the diff says so — confirm nothing moved *into* them from elsewhere).
- [x] Is `TYPE_NAMES` read anywhere except the reverse lookup, and is `COLLECTION_TYPES`' *value*
      (the type object) used at all, or only its key? A map whose values are never read is a
      simpler thing than it looks.
- [x] **Step 2 (the 15 ops).** Each signature and body against the plan's table; each docstring claim
      against behaviour (`set_add` on unhashable, `set_to_list` on `{1, "a"}`, `list_remove_at` out of
      range). The negative-index deviation (`plan.md:181-185`) — pin exactly what is reachable.
- [x] **Step 3/4 (wiring, registry).** Recompute the golden claim independently: for each of the four
      goldens, keys added / removed / changed, and that the added set is exactly `BUILTIN_FUNCTIONS`.
      Check the corrected key-order story (builtins land between plugin functions and constructors).
- [x] Re-derive the `node_types.all.json` sort-order claim (`math, phiflow, string` = `sorted(discover())`).
- [x] **Step 5 (graph).** The added type-compatibility cases; and the one case the plan does *not*
      list — `list → Any → set`, i.e. whether a laundered edge defeats check 6 in practice.
- [x] **Step 6 (end to end).** The four fixtures and three examples: do they assert values, and is
      each example still a byte copy of its fixture? (Finding 1 of the review means all seven are due
      to change; verify the copies were in sync *before* that, since nothing checks it.)
- [x] **Step 7 (docs).** Recompute the annotation-slot table from the installed surface. Re-run the
      zero-plugin suite and the full suite; compare against 187/78 and 267/0.
- [x] **`test_acceptance.py`'s cache bug.** `plan.md:278-286` claims the test had been asserting
      against a stale cached wheel and that `--refresh-package` fixes it. That is the most
      consequential deviation in the document — a test that silently verified nothing. Reproduce both
      halves: that the stale wheel was really being installed, and that the fix really refreshes.
- [x] **TODO.md.** Spot-check its counts and its "12 tautological tests" list; decide whether it
      becomes an issue now or stays parked.

Output: a findings table — claim, verdict, how it was checked.

## Step 4 — mutation pass

Method from `pr-24-review.md`: hand-pick mutants from the design decisions, edit one line, run the
single relevant file, `git checkout --` before the next. Check for equivalent mutants before
reporting a gap. Candidates, chosen so each asks one question:

| mutant | asks | expectation |
| --- | --- | --- |
| `list_append` → `lst.append(item); return lst` | is purity pinned? | must fail; if it passes, the DAG's core assumption is untested |
| `dict_set` → `d[key] = value; return d` | same, for dict | must fail |
| `set_add` → `s.add(item); return s` | same, for set | must fail |
| `set_to_list` → `list(s)` | is *sortedness* pinned, or only "returns the elements"? | **suspect an equivalent mutant** on small int sets — `list({5, 7})` is already `[5, 7]`. If the only fixture data is small ints, this is a real gap |
| `set_remove` → `discard` | is fail-loud pinned? | must fail |
| `list_remove_at` → `out[:i] + out[i+1:]` | is out-of-range fail-loud pinned? | must fail |
| `list_get` → `lst[index] if 0 <= index < len(lst) else None` | is `IndexError` pinned, or just the happy path? | must fail |
| `__init__.py`: move `update(BUILTIN_FUNCTIONS)` **before** the plugin loop | is design decision 7 pinned? | must fail |
| `primitives.py`: `TYPE_NAMES = dict(PRIMITIVES_MAP)` | is the socket typing pinned end to end? | must fail in registry *and* golden tests |
| `registry.py`: pass `TYPE_NAMES` keys as `primitives` | would a spurious `list` primitive node be caught? | must fail — goldens |
| reorder two `BUILTIN_FUNCTIONS` keys | does the byte-for-byte golden comparison really bite? | must fail |
| `list_size` → `len(lst) - 1` | do the end-to-end fixtures assert values or shapes? | must fail |
| `executor.py:101`: drop the `isinstance(value, tuple)` clause | is single-output pass-through pinned? | **expected to survive** — finding 2 |
| `executor.py:101`: drop the `< len(value)` bound | is the short-tuple guard pinned? | **expected to survive** — finding 2 |

- [x] Run each; record killed / survived / equivalent.
- [x] For every survivor, decide: missing test, or a behaviour nobody decided?
- [x] One design-level mutant, not a code one: give a fixture a `{1, "a"}` set and confirm the failure
      arrives at run time (step 2's asymmetry, demonstrated rather than argued).

Output: a mutation table in the review, and one test-gap finding per survivor.

## Step 5 — review guidelines

Source: `pr-24-review.md`'s closing sections — *Resources*, *Mutation testing*, *Concepts worth
naming* — plus what this review adds: the round-trip-through-the-real-consumer check that found
finding 1, and the "recompute every counted claim" rule.

- [x] Draft the content as a checklist a reviewer can execute, not an essay: what to run first, which
      claims to recompute, how to pick mutants, when to return a PR unreviewed, and the tone note
      (findings are about the artifact, not the author).
- [x] Keep the resource table, which is the part that does not go stale.
- [x] Encode the file convention the repo now has two instances of:
      `issues/<n>-<slug>/pr-<n>-review.md`, plus the round-2 shape.

Output: `docs/reviewing-generated-prs.md`.

## Step 6 — consolidate

- [ ] Write steps 2-4 into `pr-28-review-round-2.md`, uncommitted until you say otherwise.
- [ ] State plainly what was *not* reviewed, as `pr-28-review.md` already does.
- [ ] One question to the author, chosen from the mutation survivors — the PR #24 review's format, and
      the part that tells you how much of the PR was read rather than generated.
- [ ] **Then decide, together:** when to commit, and whether the two review files merge into one
      document or stay as two rounds. Finding 1 sits in the first file and is still the blocker either
      way, so it leads whichever shape wins.
