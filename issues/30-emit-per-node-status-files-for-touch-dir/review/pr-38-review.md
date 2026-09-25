# Review: PR #38 — per-node status markers

Round 1 of [PR #38](https://github.com/2listic/coral-python/pull/38), implementing
[`../plan.md`](../plan.md) for [issue #30](https://github.com/2listic/coral-python/issues/30).

Read at `01adf27`. Reference repos: `coral` at `653f890`, `dealiiX-platform` at `7e19bd8`.

## Verdict

**No blocking findings; nothing here needs the PR returned.** The feature works, the suite is green,
and `ec4c986` + `01adf27` already fixed most of what an earlier read of this branch turned up. One
item is worth a decision, and one costs a single test.

| # | item | kind |
| --- | --- | --- |
| 1 | `qualified_id` validation sits outside `Graph`, while the branch moved two sibling id-rules in. Six new rejection paths are absent from the documented "every check" list | design + false invariant |
| 2 | `except BaseException` is unpinned — the mutation to `except Exception` passes 65 tests. Costs nothing observable today (the platform has no cancel path), but the choice is deliberate and undefended | missing test, latent |

Then a nit, two behaviours recorded as not-defects, a pre-existing diagnostic bug that is not this
PR's code, and a note that `plan.md` has drifted from the code. Coverage: full suite, a round trip
through the editor, the validation path reproduced, one mutation — detailed under
[What was run](#what-was-run).

## Finding 1 (worth fixing here) — `qualified_id` validation sits outside `Graph`

`qualified_ids()` is still in `nodestatus.py`, still called from `WorkflowExecutor.__init__`
(`executor.py:69`). Since `ec4c986` it assigns nothing — it only validates that every node declares a
unique, filename-safe `qualified_id`, which makes it a graph check living outside the graph.

**The branch itself puts sibling rules in `Graph`.** `01adf27` moved two id-correctness rules in,
both correctly:

| rule | where it landed |
| --- | --- |
| node ids unique after `str()` coercion | `graph.py:_read_nodes` |
| no node nests a workflow — the shape where node ids stop being unique | `graph.py:_check_no_node_is_a_subgraph` (check 2) |

The third rule of the same family stayed in the executor. The subgraph check's docstring even argues
that nested ids collide and "only the `qualified_id` (`12_3`) tells them apart" — reasoning about a
field `Graph` then never validates.

**The invariant this widens.** `CLAUDE.md:458-460` and `graph.py:100` both promise: *"Constructing a
`Graph` runs every check below; a graph that constructs is a graph that can be executed."* The branch
adds six ways to reject a graph — missing, non-string, empty, contains `.`, contains a separator,
duplicated — none of them in that numbered list or in `Graph`. A graph with two nodes sharing a
`qualified_id` constructs fine and is not executable, and `tests/test_graph.py` builds bare `Graph`s
throughout.

**Two ways to close it.** Run the validation during `Graph` construction — `graph.py` importing
`nodestatus` is allowed, the contract guard forbids only the reverse
(`tests/test_core_contract.py:145-155`) — or qualify that sentence in both places. Shipping neither
leaves a documented invariant the code does not honour.

There is a real seam if the split is wanted: *declared and unique* is graph identity; *filename-safe*
(`.`, `/`, empty, non-string) is genuinely the writer's concern. Splitting literally still leaves
`"a.b"` constructing a valid `Graph` and failing later, so it does not by itself close the gap.

*Supporting, not load-bearing.* Two weaker arguments point the same way. The reason the function sits
in `nodestatus.py` was decision 6a — "the `_auto_` scheme is the file-naming convention of one
external consumer" — and `ec4c986` deleted that scheme, so the premise went while the conclusion
stayed. And C++ owns this in the graph object: `Network` validates uniqueness in `from_json`
(`coral_network_implementation.h:586-588`), stores the id on the node (L350), and exposes
`get_node_qualified_id` (`coral_network.h:152`). Both are weighted low on purpose — the first argues
from a planning document, and this branch has already shown, correctly, that C++ is worth diverging
from where it is wrong.

**Considered and not recommended:** storing the id *on the node* rather than in a
`node_id -> qualified_id` dict, as C++ does. The argument was that the key is only locally unique
while the value is globally unique — node `3` at top level and node `3` inside network node `12` are
different nodes — so the side table breaks the day nesting arrives. `_check_no_node_is_a_subgraph`
now rejects exactly that shape, which makes the side table safe by construction and the argument
purely forward-looking. Worth revisiting only alongside subgraph support; the copy-on-write question
it raised is moot while nothing mutates the node dicts.

## Finding 2 (cheap, and latent) — the `BaseException` choice is unpinned

`nodestatus.py:171` catches `BaseException`, not `Exception`. That is the correct choice and the
non-idiomatic one; nothing in the suite holds it in place.

**Reproduction.** Change line 171 to `except Exception:` and run
`pytest tests/test_nodestatus.py tests/test_executor.py` — **65 passed**. No test raises anything
outside `Exception`; `grep -n "BaseException\|KeyboardInterrupt\|SystemExit"` over both files returns
nothing.

**Stakes today: low.** The only thing `BaseException` buys over `Exception` is `KeyboardInterrupt`
and `SystemExit`, and neither is reachable from the platform — it spawns the backend at
`localCoralRuns.ts:130` and there is no `.kill()`, `SIGINT` or cancel path anywhere in `electron/` or
`src/`, so a started job runs to completion. That leaves the CLI, where Ctrl-C during a long phiflow
run would leave an orphaned `.running`. But the CLI user is reading a traceback in their terminal,
and the only consumer of the markers is the platform, which is not watching that directory. So the
mutation surviving costs nothing observable right now.

**Why fix it anyway.** It is one test, the code is already correct, and the choice is deliberate but
undefended — nothing would notice a refactor "tidying" it to the idiomatic `except Exception`. It
stops being harmless the day the platform grows a stop button, which is an obvious feature for
long-running jobs, and nobody will re-derive this analysis then.

**Suggested fix.** One test raising `KeyboardInterrupt` inside `status.node(...)` and asserting
`.failed` exists and the exception propagates unchanged. The existing
`test_the_exception_propagates_unchanged` is the shape to copy.

## Not this PR's code

Surfaced while reproducing the validation path (see [What was run](#what-was-run)). **Check 3 misdiagnoses the commonest editing
mistake**, and the check ordering it comes from predates this branch (`d55ec49`, untouched by #38).

Deleting one edge into a six-input node gives:

```
ValueError: Node '51' of type 'phiflow_iterate' has 5 incoming edges on input ports
[0, 1, 3, 4, 5]; expected exactly [0, 1, 2, 3, 4] — a port is duplicated or out of range
```

Both halves of that hint are false here. Nothing is duplicated — `[0,1,3,4,5]` are distinct — and
nothing is out of range: `phiflow_iterate` has **6** inputs (`velocity_grid, smoke_grid, time_steps,
dt, substeps, obstacles`), so port 5 is perfectly valid. The actual defect is that port 2
(`time_steps`) is unwired, which is check 4's message — *"expects 6 inputs but received 5"* — but
check 3 runs first and preempts it.

The cause is that check 3 compares the port indices against `range(len(incoming))`, the **edge
count**, rather than against the type's input count. A missing edge therefore breaks contiguity as a
*side effect* and is reported as a contiguity fault.

Three fixes, increasing scope. Reordering (b) was measured: it breaks exactly one test
(`test_port_index_out_of_range_is_rejected`, which pins check 3's wording for a graph that violates
both rules), 133 others pass.

| | change | cost |
| --- | --- | --- |
| a | compute the hint — name the missing, duplicated or out-of-range ports instead of asserting both | smallest; no test or doc churn |
| b | run check 4 before check 3 | one test regex; loses the bad-index detail when a graph violates both |
| c | have check 3 compare against the type's input count, subsuming check 4 | best messages; touches `CLAUDE.md`'s numbered list |

(a) looks right-sized. Whether it earns an issue is the author's call — it is outside this PR either
way — but it is the error a user meets after deleting or forgetting one connection, which is the most
likely way to reach any graph error at all.

## Not defects — recorded

- **A hard kill orphans a `.running`.** No Python-level cleanup runs, so `SIGKILL`, an OOM kill, or a
  native crash in JAX/phiflow leaves no terminal marker, and the platform's modal polls forever. C++
  has the same gap; the pattern cannot close it. Worth a line in the docs rather than a change.
- **The context manager is the right pattern**, though not for the reason decision 1 gives. On the
  failure guarantee it is *exactly* equivalent to an explicit
  `running / try / except → failed, raise / succeeded` in the walk — sequentially there is no failure
  mode one catches and the other does not. What it actually buys is a guarantee localised in one
  testable object, robustness to `continue`/`break`/`return` inside the block, and composability when
  the concurrency `graph.py:298` anticipates ("that batch is also where concurrent execution of
  independent branches would hook in") arrives. Worth stating plainly rather than leaving decision 1
  to imply the sequential case needs it.

## Nit

`nodestatus.py:155` annotates the context manager `-> Iterator[None]`, which resolves to the
`@deprecated` overload of `contextlib.contextmanager` in typeshed (a PEP 702 marker, hence the IDE
strikethrough). `-> Generator[None, None, None]` clears it.
## Also worth mentioning — `plan.md` no longer matches the code

Not a finding, and only worth acting on if the plan is meant to outlive the PR. `ec4c986` removed the
`_auto_` fallback, but `plan.md` still describes it in decisions 6, 6a and 6c, in Steps 1, 2 and 4,
and in *Out of scope* ("The `_auto_` fallback is implemented for coherence"). There are no deviation
notes.

It matters only where someone would re-derive a decision from it — decision 6a is the one case, since
it is the recorded reason `qualified_ids()` sits where finding 1 argues it should not. The reasoning
already written in `nodestatus.py`'s module docstring is the right replacement text if a note is
wanted.

## What was run

| | result |
| --- | --- |
| full suite, `uv run --no-sync pytest -q` | **412 passed** in 93s |
| every graph under `examples/` + `tests/fixtures/` parsed and checked | 14 files, 206 nodes, **all** carry `qualified_id` equal to the node id — `CLAUDE.md:618`'s claim holds |
| mutation: `except BaseException` → `except Exception` | **survived** — finding 2 |
| `examples/phiflow/network-from-fe.json` run from the editor | markers appear per node; the status table populates |
| node 21 (`int` primitive) given a non-numeric value, run from the editor | table shows **21 failed** |
| the `21 -> 51` edge deleted, run against a directory holding `stale.succeeded` + `keep.txt` | rejected in `Graph.__init__`; stale marker gone, `keep.txt` kept, **no marker written** |
| each failure mode raised inside `status.node(...)` | `IndexError`, `KeyboardInterrupt`, `SystemExit` → `.running` + `.failed`; `SIGKILL` → **`.running` only** |

## Verified against the real consumer

The editor round trip settles three things the Python suite cannot.

- **Primitives really do surface.** Node 21 is an `int` primitive; a non-numeric value makes
  `_convert` raise, and the table shows it failed. Decision 8 ("all nodes get markers, primitives
  included") is confirmed end to end — had primitives been exempt, that node would simply never have
  appeared.
- **The failure pair reads correctly.** `.running` + `.failed` together are displayed as failed, not
  as still-running: `getDisplayStatus` checks `FAILED` first (`NodeStatusModal.svelte:44-52`).
- **Current exports carry `qualified_id`.** Worth recording because the repo's own example did not:
  as committed at `ec4c986^`, `examples/phiflow/network-from-fe.json` (`"author":
  "dealiix-platform"`) had **0 of 29** nodes with the field, and the commit added them. That file
  predates the platform's `parseGraphWithQualifiedIds`, which at `7e19bd8` is used on all three
  export paths — execute (`sshMessages.ts:364`), download (`SidebarButtons.svelte:367`) and save
  (`SaveProjectForm.svelte:29`). So `CLAUDE.md:430`'s warning describes older exports, and no cliff
  exists with the current editor.

**The validation path holds.** Deleting the `21 -> 51` edge and running against a directory
pre-loaded with `stale.succeeded` and `keep.txt`: the graph is rejected in `Graph.__init__`, the
stale marker is gone, `keep.txt` survives, and **no marker is written**. Decision 3 — prepare the
directory on the first line of `__init__`, before validation — does exactly what it was placed there
for: the platform sees an empty directory, not the previous job's timeline.

**The UI half is answered, and the answer is a platform bug** — filed as
[dealiiX-platform#217](https://github.com/2listic/dealiiX-platform/issues/217). Issue #30 asked
whether an empty directory reads as "nothing ran" or as "still starting". It reads as **neither**:
`NodeStatusModal` keeps the previous job's rows when a job writes no markers, and its poll's stop
condition — derived from that stale map — then returns before the first fetch, so nothing corrects
it.

Evidence: `local_runs/run-test-nodestatus-fail3/nodes-exec-status/377` and
`run-test-set-collection-after-review/nodes-exec-status/371` both hold **0 entries**, and 371
predates this branch entirely, yet both display data.

Nothing here is coral-python's to fix. The consequence for this PR is only that **the
failed-before-starting case cannot be observed end to end** until #217 lands — the backend half of it
is verified in the row above.

## Already fixed by the last two commits

Recorded because it is most of what an earlier read of this branch turned up, and it explains why
this review is short.

- **The `_auto_` fallback is gone** (`ec4c986`); a missing `qualified_id` is now a `ValueError`, and
  that is a better outcome than the deferral it was heading for. `<node_id>_auto_<counter>`
  fabricated nesting that does not exist — the platform joins ancestor ids with `_`
  (`graphParser.ts:375-377`) and splits on every `_` to render the breadcrumb
  (`NodeStatusModal.svelte:54-57`), so `5_auto_0` would have displayed as `5 → auto → 0` for a flat
  graph. Diverging from C++ here is right, and `nodestatus.py`'s docstring gives the reason: an
  invented name is not the node's identity.
- **Filename safety is enforced** — non-string, empty, `.`, and path separators, each with its own
  message. The `.` rule is the one the consumer actually depends on (`sshMessages.ts:688`).
- **`tests/test_executor.py`'s `"top/first"` case is gone** — it had enshrined as supported a shape
  the only consumer never produces.
- **Node ids are genuinely verified unique**, not merely unique by dict semantics: `_read_nodes`
  coerces with `str()` and raises on a post-coercion collision, closing the `0` vs `"0"` gap.
- **A nested-workflow node is rejected by name**, so it no longer surfaces as "unknown type
  `coral::Network`".


## Follow-ups filed

| where | what |
| --- | --- |
| [dealiiX-platform#217](https://github.com/2listic/dealiiX-platform/issues/217) | `NodeStatusModal` shows the previous job's rows when a job produces no status files, and then stops polling. Blocks *observing* the failed-before-starting case; not a backend defect |

Check 3's misdiagnosis is left for the author to file or not — pre-existing, and outside this PR
either way.

## Still owed

Nothing on the backend. The failed-before-starting case cannot be *observed* end to end until #217
lands, which is a platform change rather than a reason to hold this PR.

Only one mutant was run. Candidates not yet tried: the `is_file()` guard in the cleanup (does
anything pin that a *directory* named `x.succeeded` survives?), the warn-once flag, and the
unconditional build of the qualified-id mapping when `touch_dir=None`.
