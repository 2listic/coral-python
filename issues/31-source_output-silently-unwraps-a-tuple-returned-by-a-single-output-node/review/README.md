# Review of PR #36 — summary

Review of [PR #36](https://github.com/2listic/coral-python/pull/36), which fixes
[issue #31](https://github.com/2listic/coral-python/issues/31) following the plan in
[`../plan.md`](../plan.md). One round; the debugger step from
[`docs/reviewing-generated-prs.md`](../../../docs/reviewing-generated-prs.md) was skipped as
unnecessary for a fix this size and shape — see [What was not run](#what-was-not-run).

## Verdict

**No defects found.** The fix matches the plan exactly, the real-consumer checks came back clean, and
every mutation targeting a design decision was killed — see below.

## Follow-ups

None filed from this review. [Issue #37](https://github.com/2listic/coral-python/issues/37) (docstrings
citing issue/PR numbers) was opened separately during this review but is unrelated to #31's correctness
— a documentation-hygiene issue found by inspection, not a finding against this PR.

## What was checked

**Real consumer.** Not the editor itself (no instance available to this review), but the two things
that stand in for it:

- Regenerated the `math` and `phiflow` registries with the real CLI (`coral -p <plugin> register`)
  and diffed them against `tests/golden/` — byte-identical. The registry format the DealiiX editor
  reads is untouched, which is expected: no in-tree annotation is degenerate, so step 1 of the plan
  changes nothing it renders.
- Ran `examples/phiflow/network-from-fe.json` for real (`pytest -k phiflow`, an actual PhiFlow/JAX
  simulation, ~33s) rather than trusting the plan's claim that `phiflow_iterate` already agrees with
  its `Tuple[Any, Any, Any]` annotation. It does — the new arity check passes against its genuine
  3-tuple return, on a graph where none of `phiflow_iterate`'s outputs are wired to anything. That's
  exactly the "fires whether or not the port is wired" design point (decision 2), exercised live
  rather than only in a unit test.

**Design vs. plan.** Each of the plan's 5 steps maps cleanly onto the diff:

| step | claim | checked |
| --- | --- | --- |
| 1 | `nodeports.py` rejects `Tuple`/`Tuple[()]`/`Tuple[Any, ...]`, names the node type, leaves plain `tuple` and declared `Tuple[...]` alone | code reads exactly this; `node_type` is threaded through `_function_ports`/`_method_ports` into the error |
| 2 | `_input_values` asks the port table (`len(outputs) > 1`) instead of `isinstance(value, tuple)` | confirmed; no `is not None` guard, no bound check remain |
| 3 | `_check_output_arity` runs right after every non-primitive call, `ValueError` naming node id/type/counts, only `n > 1` checked | confirmed; also checked it's a structural no-op for constructors and primitives (always ≤1 output), not an oversight |
| 4 | tests per the plan's table, no plugin marker needed | both test files match; `executor_over` builds a real `WorkflowExecutor` through `__init__`, not `__new__` |
| 5 | `CLAUDE.md` updated in the three places named | confirmed |

Also confirmed, since it's the thing the whole fix leans on: `graph.py`'s existing check 5 already
rejects `-1` on a multi-output node and bounds `source_output` to `0 .. len(outputs)-1`, so
`_input_values`'s new unconditional index is never out of range by construction — decision 1a (no
re-check in the executor) holds.

**Mutation testing.** 5 mutants targeting the design decisions, all killed, tree clean after each:

| mutant | targets | result |
| --- | --- | --- |
| revert `_input_values` to the pre-fix `isinstance`/bound logic | decision 1 | 3 tests fail |
| `_check_output_arity`: `expected <= 1` → `< 1` (stop skipping n==1) | decision 2a | 8 tests fail |
| `_check_output_arity`: `len(result) != expected` → `< expected` (miss over-long tuples) | decision 2 | 1 test fails |
| `nodeports.py`: drop the `Ellipsis in args` half of the rejection | decision 3 | 1 test fails |
| `nodeports.py`: drop the `not args` half of the rejection | decision 3 | 4 tests fail |

The two mutants the issue explicitly asked for (dropping the `isinstance` clause, dropping the
`< len(value)` bound) are the first one above and mutant 3 respectively — both caught.

Full suite: 342 passed, 0 failed, 0 skipped.

## What was not run

The debugger walkthrough this repo's review process otherwise opens with. Three reasons, together:

- This PR is a direct follow-up of PR #28 — issue #31 itself was found *during* the PR #28 review, in
  `executor.py` code that actually shipped with PR #24. Both of those already got a debugger pass
  (`issues/23-refactor-executor/pr-24-review.md`,
  `issues/25-.../review/debug-walkthrough.md`), stepping through the exact `_input_values` /
  execution-order machinery this fix sits inside. There is no fresh execution path here for a
  debugger to reveal that those runs didn't already cover.
- The code was read and checked by hand line by line against the plan (see the table above), not
  skimmed.
- What a debugger session would add — proof that the real execution path behaves as claimed — was
  obtained instead by running an actual PhiFlow simulation through the unmodified CLI/executor and by
  mutating the actual decisions, both closer to ground truth than a manual stop-and-inspect pass over
  the same lines.

Flagged here per
[`docs/reviewing-generated-prs.md`](../../../docs/reviewing-generated-prs.md#returning-a-review-unread)'s
convention of saying plainly what wasn't reviewed.
