# Plan: emit per-node status files for `--touch-dir`

Implements [issue #30](https://github.com/2listic/coral-python/issues/30). That issue holds the
contract and the platform-side references; the decisions reached in discussion are recorded below,
then the steps.

Every decision was taken against one criterion the discussion settled on early: **coherence with the
C++ reference backend**, which is the producer the platform's consumer was written for. Where this
plan departs from the issue's own wording, it is because the C++ source says otherwise — see
[What the C++ backend actually does](#what-the-c-backend-actually-does).

## What the C++ backend actually does

Read at `coral-editor@66dda72` (`/home/matteo/Projects/dealII-X/repos/coral-editor`). Four findings
shaped the decisions, two of them contradicting assumptions we started from:

| # | finding | reference |
| --- | --- | --- |
| 1 | **There is no "write nothing" mode.** The CLI defaults `touch_file_path` to `"./"` and calls `set_touch_file_base_path` unconditionally; `touch_file()` has no "is it configured" guard. With the flag omitted, the C++ backend writes markers into the **cwd** and cleans the cwd at startup. | `core/source/backend_main.cc:541,563-572,665` |
| 2 | **`qualified_id` is optional, and the fallback is not the node id.** If the field is absent the loader generates `<node_id>_auto_<counter>`, warns per node, and marks it so it is never serialised back. If present, **uniqueness is enforced** across nodes (`DuplicateQualifiedIdException`). | `core/include/coral_network_implementation.h:562-609,1065-1075`; `core/include/coral_network.h:19-34` |
| 3 | **Every node is a task.** `rebuild_taskflow` emplaces one task per entry in `nodes` and each goes through `execute_node_task` — constants included, no exemption. | `core/include/coral_network_implementation.h:247-259` |
| 4 | **Status I/O is asymmetric.** `create_directories` throws and aborts the run; `std::ofstream{path, app}` sets failbit and is never checked, so a per-node touch that fails is silent. | `core/include/coral_network_implementation.h:30-49,157-198` |

The producer itself: `set_touch_file_base_path` (L157-198) creates the directory if missing, else
deletes the regular files in it whose name ends in `.running`, `.succeeded` or `.failed` — and
nothing else. `execute_node_task` (L208-236) touches `.running` before the node, `.succeeded` after,
`.failed` on exception; a failed node therefore leaves **both** `.running` and `.failed`. Files are
empty.

The consumer (`dealiiX-platform`, `src/lib/utils/sshMessages.ts::getNodesExecutionStatus`) lists the
directory with `ls -tr`, so file mtime order *is* the status timeline, and recovers the key with
`line.split('.')` — which is why a `.` in a qualified id mis-keys silently.

## Decisions

| # | question | decision | why |
| --- | --- | --- | --- |
| 1 | what does the executor call per node? | **a context manager**, `with status.node(qid):` — enter writes `.running`, clean exit `.succeeded`, exception writes `.failed` and propagates | one added line in the walk; "`.failed` is written before the exception escapes" becomes a property of one object, testable on its own, instead of a discipline `execute()` must keep |
| 1a | null object or `Optional`? | **`Optional[NodeStatusDir]`**, `nullcontext()` when absent | one class instead of two; see [The call site](#the-call-site) |
| 2 | how does the touch dir reach the executor? | **as a path**: `WorkflowExecutor(graph, plugins=None, touch_dir=None)`, which builds the collaborator itself | mirrors how `plugins` already works (CLI forwards a raw value, executor resolves it), keeps all filesystem I/O out of `cli.py`, and leaves us free to place the cleanup relative to plugin loading and validation (decision 3) |
| 3 | when are mkdir + cleanup done? | **first line of `__init__`**, before plugin loading and before graph validation | what C++ does (setup, before execution); makes a validation failure show the platform an *empty* directory rather than a stale timeline from an earlier job; fails fast on a bad path before phiflow is imported |
| 4 | flag omitted — where do markers go? | **the cwd**, exactly as C++ (finding 1) | the criterion is coherence, and the reference backend has no silent mode. Consequences accepted: `coral run` in a checkout drops markers there and cleans matching files; two concurrent runs in one cwd share a directory (the platform avoids this with `<internalJobId>`) |
| 5 | who owns the `"./"` default? | **the CLI** (`argparse default="./"`); `WorkflowExecutor`'s `touch_dir=None` means "write nothing" | the platform contract is the *CLI*, so fidelity has to hold there and does. `WorkflowExecutor` stays a library object that does no surprise I/O, so the existing executor and integration tests keep passing without each being handed a `tmp_path` |
| 6 | what id names the file? | **`qualified_id` from the node**, falling back to C++'s `<node_id>_auto_<counter>` scheme | finding 2. The `_auto_` form is noise for a flat graph whose ids are already unique, but the criterion is coherence and this is observable behaviour, not an internal detail |
| 6a | who computes the mapping? | **`nodestatus.py`**, as a pure `qualified_ids(nodes) -> dict` the executor calls once | the `_auto_` scheme is the file-naming convention of one external consumer — exactly the kind of thing `registry.py` exists to keep out of `graph.py`. As a free function it is unit-testable without a graph or a directory |
| 6b | duplicate `qualified_id`? | **`ValueError` naming it**, and the mapping is built **unconditionally**, touch dir or not | what C++ does at load. Two nodes sharing a filename would corrupt the very timeline the feature exists to show, silently |
| 6c | the "missing `qualified_id`" warning | **one line per run**, listing the count and a sample | C++ warns per node; on our own graphs (none carry the field) that is a wall of text before execution starts. Same information, no noise |
| 7 | what propagates after `.failed`? | **the original exception, untouched**, plus a printed line naming the node | see [Why not C++'s wrapped exception](#why-not-cs-wrapped-exception) |
| 8 | which nodes get markers? | **all of them, primitives included** | finding 3. A graph whose primitives never appear reads as "half the nodes never started" |
| 9 | status I/O that fails? | **abort at t=0** (mkdir/cleanup), **warn once and keep executing** mid-run | finding 4. A bad `--touch-dir` is a configuration error and costs nothing to fail on; once nodes are running, the graph's result is worth more than its telemetry |

## The call site

`execute()` gains one line, and the `Optional` is resolved once per run rather than per node:

```python
status = self.status.node(qid) if self.status else nullcontext()
with status:
    ...            # the whole per-node body, primitive branch included
```

The primitive branch's `continue` exits the block cleanly, so it writes `.succeeded` —
`contextlib.contextmanager` handles that correctly. Anything raising inside the block — a plugin
function, `_check_output_arity`, the method-instance check — writes `.failed` and propagates.

The rejected alternative was three explicit methods (`running` / `succeeded` / `failed`) with a
`try/except/raise` in the walk: louder at the call site, but it puts exception handling into a method
whose docstring says there is nothing left to verify, and it makes the "`.failed` before the raise"
guarantee a property of the executor rather than of one testable object.

## Why not C++'s wrapped exception

C++ re-throws with node context: `throw std::runtime_error("Node N [qid] failed: " + e.what())`.
We do not, on a structural ground:

Under decision 1a the `try/except` lives *inside* the context manager, which exists only when a touch
dir is configured. Wrapping would therefore make the exception's **type and message depend on whether
`--touch-dir` was passed** — `coral run` (always `"./"` after decision 5) would raise
`RuntimeError: Node 3 [3] failed: declares 3 outputs but returned a tuple of 2`, while the same graph
run from Python raises the bare `ValueError`. A diagnostic that changes shape with an unrelated flag
is worse than one that lacks a node id. It would also break the five assertions at
`tests/test_executor.py:534-566`, which pin the exact wording settled in issue #31.

The node context is recovered the other way, unconditionally: a printed line before the call and
after it, mirroring C++'s `slog_info` pair, so the log brackets the failure whatever the flag says.

## What is written, exactly

| moment | file | note |
| --- | --- | --- |
| before a node runs | `<qid>.running` | empty |
| node returned | `<qid>.succeeded` | empty |
| node raised | `<qid>.failed` | empty; `.running` is **left in place**, as in C++ |

No file is ever written twice within a run — the three names differ and the directory was cleaned at
startup — so `Path.touch()`'s mtime semantics never diverge from C++'s `ofstream{path, app}`, and the
consumer's `ls -tr` timeline is exactly the call order.

## Steps

### Step 1 — `packages/coral-app/src/coral_app/nodestatus.py` (new)

- `qualified_ids(nodes: Mapping[str, dict]) -> Dict[str, str]`, a pure function:
  - nodes visited in graph-JSON declaration order, so the result is deterministic;
  - an explicit `qualified_id` is used verbatim; a duplicate raises `ValueError` naming it;
  - an absent one gets `f"{node_id}_auto_{counter}"` with a single counter shared across nodes,
    advanced while the candidate collides with an already-seen id;
  - returns the mapping; the caller reports the auto-generated ones (decision 6c).
- `class NodeStatusDir`:
  - `__init__(directory)`: `mkdir(parents=True, exist_ok=True)`, then unlink the regular files whose
    suffix is one of the three. Nothing else is touched — not other files, not subdirectories. Errors
    propagate (decision 9).
  - `node(qualified_id)`: `@contextmanager` — `.running`, `yield`, `.failed` + `raise` on
    `BaseException`, else `.succeeded`.
  - `_touch()`: creates an empty file; an `OSError` here is swallowed after warning **once per
    `NodeStatusDir`** (decision 9).
- Imports nothing from `graph` or `executor`.

### Step 2 — `packages/coral-app/src/coral_app/executor.py`

- `__init__(self, workflow_file, plugins=None, touch_dir=None)`:
  - **first**: `self.status = NodeStatusDir(touch_dir) if touch_dir else None` (decision 3);
  - after the graph is built: `self.qualified_ids = qualified_ids(self.graph.nodes)`, unconditionally
    (decision 6b), and the one-line warning if any were auto-generated (6c).
- `execute()`: the two lines from [The call site](#the-call-site) around the existing body, plus the
  "start running node N [qid]" print before the call.
- No new filesystem imports here — `pathlib` and `os` stay in `nodestatus`.

### Step 3 — `packages/coral-app/src/coral_app/cli.py`

- `--touch-dir`: `default="./"`, and `nargs="?"` with `const="./"` so a bare `--touch-dir` is
  accepted as C++'s `->expected(0, 1)` accepts it. Help text rewritten — it currently says "not yet
  emitted".
- `run` passes `touch_dir=args.touch_dir` through to `WorkflowExecutor`.

### Step 4 — tests

| file | cases |
| --- | --- |
| `tests/test_nodestatus.py` (new) | directory created with parents; cleanup removes only the three suffixes, leaving other files and subdirectories alone; `.running` on enter and `.succeeded` on clean exit; on exception `.failed` **and** `.running` both present and the exception propagates unchanged in type and message; files are empty; a mid-run touch failure (directory removed after construction) warns once and does not raise; an unwritable path raises at construction |
| `tests/test_nodestatus.py` | `qualified_ids()`: all present → verbatim; all absent → `<id>_auto_<n>`; mixed; duplicate explicit → `ValueError`; an auto candidate colliding with an explicit id → the counter advances |
| `tests/test_executor.py` | with `touch_dir=tmp_path`: one `.succeeded` per node, primitives included; a failing graph leaves `.running` + `.failed` on the culprit, `.succeeded` upstream, nothing downstream; `touch_dir=None` writes nothing; a graph that fails validation leaves the directory existing and **empty**, with pre-existing stale markers already cleaned (decision 3) |
| `tests/test_cli.py` (new) | `coral run` with no flag writes the markers into the cwd (`monkeypatch.chdir(tmp_path)`) — the only test of the C++-faithful default |
| `tests/test_core_contract.py` | new guards: `nodestatus.py` imports neither `graph` nor `executor`; `executor.py` imports no `pathlib`/`os` — filesystem I/O stays in `nodestatus` |

Every new docstring follows the GIVEN/WHEN/THEN convention.

### Step 5 — documentation

- `CLAUDE.md`: a "Per-node execution status" subsection (the three markers, the cwd default, the
  `qualified_id`/`_auto_` scheme, the failure path, the two asymmetries of decision 9); `nodestatus.py`
  added to the Package layout tree; the stage-4 row of the data-flow table, which now has a side
  effect; the `--touch-dir` line in the CLI section.
- `docs/ONBOARDING.md`: line 114 (CLI synopsis), the "Per-node execution status" bullet at 503-505
  ("doesn't yet write anything there"), and the roadmap entry at 636 — the last moves out of
  Roadmap.

## Out of scope

- Streaming intermediate results or logs — the issue is only the three markers.
- Subgraph nodes: coral-python has none, so `qualified_id` never nests. The `_auto_` fallback is
  implemented for coherence, not because we can produce a nested id.
- Making the platform's UI distinguish "failed before any node ran" from "still starting" — the issue
  flags it as worth confirming on the platform side; nothing here changes for it beyond decision 3
  guaranteeing the directory is empty rather than stale.
