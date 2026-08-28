# Review: PR #28 — collection nodes

Working notes on [PR #28](https://github.com/2listic/coral-python/pull/28), which implements
[`plan.md`](../plan.md) against [`desiderata.md`](../desiderata.md) for
[issue #25](https://github.com/2listic/coral-python/issues/25).

Status: **returned to the author. Review not completed.** One blocking defect was found before the
code review began, and it is of a kind the author is better placed to scope than the reviewer. This
document is a rejection of the review request, not a review: nothing below is a judgement on the
feature, and the code has not been read.

## Scope

PR #24 is now merged (`466b299`), so the PR's 26 commits reduce to a diff against `main` that is
PR #28's own contribution: **31 files, +3632 / −125**.

| area | files |
| --- | --- |
| new module | `builtin_nodes.py` (177) |
| touched host | `__init__.py`, `primitives.py`, `registry.py` |
| new tests | `test_builtin_nodes.py` (372), `test_examples.py` (91) |
| touched tests | `test_graph.py`, `test_integration.py`, `test_registry.py`, `test_plugins.py`, `test_plugin_discovery.py`, `test_acceptance.py`, `conftest.py` |
| new fixtures | 4 × `network-collections-*.json` |
| new examples | `examples/collections/{list,set,dict}.json` |
| goldens | `node_types.all.json` rewritten, 3 per-plugin goldens added |
| docs | `CLAUDE.md`, `docs/ONBOARDING.md`, 3 files in `issues/25-.../` |

PR #24's own findings are in [`../23-refactor-executor/pr-24-review.md`](../../23-refactor-executor/pr-24-review.md)
and are not repeated.

## Why this is returned rather than reviewed

The examples this PR adds do not survive the round trip through the DealiiX platform, which is the
only consumer this backend has. That was found on the first end-to-end run, before reading the code.

The rule it breaks is not in dispute: a node id is a string that converts to an integer, as agreed
between reviewer and author. What is open is how far the wrong assumption reaches through this PR and
whether coral-python should start enforcing the rule. Answering that here would hand back a decision
already taken and leave the reviewer reviewing their own choice.

## Finding 1 (blocking) — the new examples use non-numeric node ids; the protocol keys nodes by integer

`examples/collections/{list,set,dict}.json` and the four `network-collections-*.json` fixtures use
word ids (`empty`, `with_five`, `five_again`). Every node id in all seven files is non-numeric.

**The contract.** A node id must convert to an integer — the convention already agreed for this
project, and what the reference C++ backend enforces on read
(`coral/core/include/coral_network_implementation.h:569`):

```cpp
int id = std::stoi(key); // Convert string key to int
```

`Network::nodes` is keyed by `unsigned int` and `Connection` takes `unsigned int` endpoints, so this
is the protocol's shape, not a local parsing choice. `std::stoi("empty")` throws. coral-python takes
the opposite position — `graph.py::_read_edges` coerces endpoints with `str()` and treats ids as
opaque — so these graphs run here and nowhere else.

**Symptom, reproduced.** Load `examples/collections/set.json` in the platform editor and run it
locally. The graph the platform writes has every edge's endpoints null
(`local_runs/run-test-set-collection-*/graph-370.json`):

```json
"0": {"source": null, "target": null, "source_output": 0, "target_input": 0}
```

Node ids, positions, `target_input` and edge count all survive; only the endpoints are lost. The
exporter coerces them at `src/lib/utils/graphParser.ts:360-361`:

```ts
source: parseInt(obj.source),
target: parseInt(obj.target),
```

`parseInt("empty")` is `NaN`, and `JSON.stringify(NaN)` is `null`. Our own loader then reports it
accurately:

```
ValueError: Edge '0' names source node 'None', which the graph does not declare
```

That message is `graph.py` working correctly — `str(None)` is `'None'`. The `parseInt` is the
exporter honouring the same integer contract the C++ backend does, so it is not the bug.

**The defect is this one field.** Restoring the endpoints on the platform's own exported file and
running it unchanged executes the whole graph — `with_duplicate = {5, 7}`, `as_list = [5, 7]`,
`size = 2`, `smallest = 5`, `empty` still `set()` in `results`. So the two platform-facing novelties
the PR flags in `CLAUDE.md` — zero-input function nodes, and `"set"`/`"list"` as socket types with no
`registry[...]` key — both round-trip correctly, and nothing here is evidence against the feature.

Reproduce:

```bash
python3 - <<'PY'
import json
run = "<dealiiX-platform>/local_runs/run-test-set-collection-1787732111374/graph-370.json"
g = json.load(open(run)); e = json.load(open("examples/collections/set.json"))
for (k, edge), o in zip(g["workflow"]["edges"].items(), e["workflow"]["edges"].values()):
    edge["source"], edge["target"] = o["source"], o["target"]
json.dump(g, open("/tmp/repaired.json", "w"))
PY
uv run coral -p "math" run /tmp/repaired.json
```

**Two further effects, read from the platform source rather than observed in the app.** Both are
worth the author's attention because they are silent where the export at least fails loud:

| where | mechanism | effect |
| --- | --- | --- |
| `src/lib/stores/nodes.svelte.ts:105-109` | `nodes.reduce((max, node) => Math.max(max, parseInt(node.id)), -1)`, called on every graph load (`graphParser.ts:63`), on subnetwork navigation and on undo-stack restore | one non-numeric id makes the reduce `NaN`; `NaN` is absorbing, so the id counter never recovers and `String(lastNodeId + 1)` is `"NaN"`. Every node added after loading such a graph would get the same id. Verified by evaluating that expression over `set.json`'s ids, not by clicking in the editor — the author should confirm it in the app before treating it as fact |
| `graphParser.ts:388-393`, `sshMessages.ts:687` | `qualified_id` joins ancestor ids with `_`; the node-status file name is `<qualified_id>.<status>` and is parsed with `line.split('.')` | uniqueness across nesting levels holds only while no id segment contains `_`; a top-level `with_five` is indistinguishable from node `five` inside subnetwork `with`. An id containing `.` mis-keys the status parse. Latent, not observed — integer ids make both unreachable by construction |

So there are three independent mechanisms resting on one invariant — *every id segment is a decimal
integer* — and only the C++ backend enforces it.

**What the author needs to decide** (the reviewer takes no position): whether coral-python should
enforce the rule, so that a graph the editor and the C++ backend cannot accept fails here too. Today
it accepts one. The cost to weigh is readable test data and error messages against a second backend
silently diverging from the protocol.

**One piece of evidence that was already in the repo.** `examples/phiflow/network-from-fe.json` is
the one example that came *from* the editor, and its ids are `"7"`, `"13"`, `"14"`. It is also what
the fixture naming (`network-from-fe-*`) and `tests/fixtures/valid_workflows/README.md` point at as
the editor-exported reference. The new examples departed from the only precedent in the repo without
recording that they had.

**The question to ask the author:** were any of these graphs opened in the editor before the PR was
raised? `plan.md:322-328` records the examples as "verified through the real CLI", and the CLI is
where this passes. Nothing in the plan, the deviations, or `test_examples.py` mentions the platform,
which is the audience the examples exist for.

## Not in this review

Everything else. Named only so the next pass has a starting list, not as a claim about any of it:

- `builtin_nodes.py` line by line, and the 15 builtins' semantics beyond what the set example ran.
- `registry.py`'s changes and the four goldens, which are the largest single diff in the PR.
- The `PRIMITIVES_MAP` / `COLLECTION_TYPES` split.
- `test_builtin_nodes.py` (372 lines), `test_examples.py`, and the mutation-testing pass that
  [`../23-refactor-executor/pr-24-review.md`](../../23-refactor-executor/pr-24-review.md) applied to
  PR #24's modules.
- Documentation accuracy. The PR's docs make counted claims (`120` annotation slots, `86` checkable,
  the per-source table in `CLAUDE.md`); none were checked. Per PR #24's review stance, treat
  quantitative claims in the docs as hypotheses.

## Adjacent, not blocking

- **Where the protocol contract lives** — one document shared by coral, coral-python and the
  platform, or a copy in each — is its own discussion and is deliberately not asked of this PR. It
  is only worth noting that no document in this repo states the integer-id rule today, which is part
  of why a reviewer had to reconstruct it from the C++ source.
- [#30](https://github.com/2listic/coral-python/issues/30) — `coral run` accepts `--touch-dir` and
  emits nothing, so the platform's per-node status view is empty for the whole run. Pre-existing,
  filed while reviewing this PR because tracing the node-id contract went through the same code. It
  depends on node ids being usable as filenames, so finding 1 is upstream of it.
- [#26](https://github.com/2listic/coral-python/issues/26) — reconciling newly added examples with
  the project structure. `examples/collections/` is exactly that, and each of the three examples is
  a byte copy of a fixture with nothing checking they stay in sync (`plan.md:345-348` records the
  cost and accepts it). Worth deciding whether the copies belong to #26 or to this PR.
