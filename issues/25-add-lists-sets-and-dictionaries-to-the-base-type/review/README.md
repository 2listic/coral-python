# Review of PR #28 — summary

Start here. The detail is in the other three files; this page is the whole result in one screen.

| file | what it is |
| --- | --- |
| [`pr-28-review.md`](pr-28-review.md) | round 1 — the review request returned on one blocking finding, before any code was read |
| [`pr-28-review-round-2.md`](pr-28-review-round-2.md) | round 2 — the code review: design, implementation, tests under mutation |
| [`pr-28-review-plan.md`](pr-28-review-plan.md) | the plan round 2 executed, with every step ticked |
| [`debug-walkthrough.md`](debug-walkthrough.md) | six debugger stops that show the added logic running |

## Verdict

**Nothing blocking remains.** The feature works, the design holds up, and the tests pin the properties
it depends on.

| | finding | state |
| --- | --- | --- |
| 1 | graph files used non-numeric node ids, so they could not round-trip through the editor | **fixed** in `622c94b` and verified — the author also renamed edge keys and added a guard test |
| 2 | `source_output` silently unwraps a tuple from a single-output node | not this PR's code (PR #24's `executor.py`) → [#31](https://github.com/2listic/coral-python/issues/31) |
| 3 | the collections↔math fixture loses two edges when loaded in the editor | the fixture is correct; the editor's rule is the problem → [dealiiX-platform#215](https://github.com/2listic/dealiiX-platform/issues/215) |

**One change worth making here**, one line: the comment above `COLLECTION_TYPES` in `primitives.py`
says "JSON cannot express a literal set or dict". The C++ backend does exactly that
(`"value": "[1, 2, 3, 4, 5]"`, parsed by the declared type), so the comment forecloses an option that
is actually open — see round 2 §2.5.

Everything else is a follow-up, listed at the bottom.

## What was checked

- **Every countable claim in `plan.md` and `CLAUDE.md` was recomputed.** All of them hold, including
  the annotation-slot table (120 slots, 34 `Any`, 86 checkable) and the golden diff (15 keys added, 0
  removed, 0 changed). Round 2 §3.
- **13 mutants, 12 killed.** The one survivor is the guard already tracked in #31. The suite even
  survives the trap I expected it to fall into — its `set_to_list` test uses string elements
  specifically so iteration order differs from sorted order. Round 2 §4.
- **The zero-plugin contract really holds**: with all three plugins uninstalled, 239 passed, 79
  skipped, 0 failed.
- **The design was judged against the rest of the system**, not only against its own plan: both
  "platform bets" are now closed, and the C++ backend's very different collection model is documented
  in §2.5.

## Two things the code cannot do yet

Neither is a defect; both bound what the feature is useful for today.

1. **No plugin can receive a collection.** Across all three plugins there is not one port typed
   `list`, `set` or `dict`. A collection is consumable only by the 15 builtins; a plugin sees elements
   one at a time through an `Any` socket.
2. **No literal form.** A collection is built by chaining `*_new` + `*_add` nodes. The C++ backend
   instead registers `std::set<unsigned int>` as an elementary type and carries the literal in a
   primitive node's `value`. The two models are complementary — and the two backends' collection
   surfaces currently do not overlap at all.

## Follow-ups

| | where |
| --- | --- |
| `source_output` tuple unwrapping | [#31](https://github.com/2listic/coral-python/issues/31) |
| surface a node's `name` (ids address, names describe) | [#32](https://github.com/2listic/coral-python/issues/32) |
| `nodeports.py` — one helper for three copies of the same step | [#33](https://github.com/2listic/coral-python/issues/33) |
| a class annotation renders as `any`, so class wiring is unchecked in the editor | [#34](https://github.com/2listic/coral-python/issues/34) |
| the editor's edge check disagrees with this backend, and drops edges on import | [dealiiX-platform#215](https://github.com/2listic/dealiiX-platform/issues/215) |
| emit per-node status files for `--touch-dir` | [#30](https://github.com/2listic/coral-python/issues/30) |
| collection parity with the C++ elementary types (a literal collection primitive) | [#35](https://github.com/2listic/coral-python/issues/35) |

Two more are recorded here rather than filed, since neither is urgent and the tracker is better kept
for work someone intends to do:

- **No plugin port accepts a collection** (zero `list`/`set`/`dict` ports across all three plugins), so
  the interop case has nothing exercising it through a typed port — §2.5.
- **Two documentation touches**: purity covers the container and not its elements (§2.3), and an `Any`
  edge launders a type mismatch that then succeeds by duck typing (§3). Worth folding into whatever
  docs change comes next.
