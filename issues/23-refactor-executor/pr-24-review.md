# Review: PR #24 — executor refactor

Working notes for reviewing [PR #24](https://github.com/2listic/coral-python/pull/24), which implements
[`plan.md`](plan.md) against [`architecture.md`](architecture.md).

Status: **in progress.** Each finding states what was reproduced and how.

## Scope

**14 files, +2784 / −387** at the point of review (before this document was committed to the branch).

| area | files |
| --- | --- |
| new modules | `nodeports.py` (199), `graph.py` (332) |
| rewritten | `executor.py`, `registry.py` (138) |
| new tests | `test_graph.py` (652), `test_nodeports.py` (291) |
| touched tests | `test_executor.py`, `test_core_contract.py`, `conftest.py` |
| docs | `CLAUDE.md` (+203), 4 new files in `issues/23-refactor-executor/` |

## What this PR gets right

- **The port table removes a real duplication.** Registry and executor each derived a node's arity
  before; now one module does. The byte-identical golden files are strong evidence the registry's output
  did not move.
- **Validating in `Graph.__init__` is the right call.** `WorkflowExecutor(...)` now fails before the
  first node runs, and it fixes the three concrete wiring bugs documented in
  [`executor-ordering-analysis.md`](executor-ordering-analysis.md): `target_input` out of range, two
  edges on one port, and an opaque `KeyError` on a dangling edge.
- **`graph.py` taking the port table as plain data is a clean seam.** No `inspect`, no plugin import, and
  its tests need no plugin installed. The `test_core_contract.py` guards make the boundary stick.
- **Error messages name the offending node or edge by its JSON key.** That is the difference between a
  usable diagnostic and "cycle detected".

## Review stance

The four markdown files are **part of the artifact under review, not evidence about it**. They read as
authoritative — tables, counts, "verified", "measured" — but were produced by the same process as the
code. [`plan.md:250-253`](plan.md) records the PR catching one of its own confabulated counts
(80/49/31 → 83/59/24); two more doc-vs-code discrepancies are in
[Non-blocking doc fixes](#non-blocking-doc-fixes). Treat quantitative and "verified" claims as
hypotheses with a one-line reproduction.

Corollary: prose defending a mechanism is a reason to check the mechanism, not to skip it. See
finding 3. The tests hold up well under mutation (12 of 13 mutants killed), but they track the documented
cases closely, so the one gap is where the documents are silent — finding 1.

## Findings

### 1. `_is_compatible` accepts `int → bool` but rejects `float → bool`

```
int   -> bool  : accept   (numeric ranks 0 -> 0)
float -> bool  : REJECT   (numeric ranks 2 -> 0)
```

An `int` primitive holding `5` wired into a `bool` parameter passes validation. Nothing coerces it, so
the plugin receives `5` where it declared `bool`: `if flag is True` misbehaves silently, `if flag:` works
by accident. A `float` in the same position is rejected.

There is no principle behind the asymmetry. It falls out of `bool` and `int` both landing on
`numbers.Integral`, so `_numeric_rank` gives them the same rank and `source_rank <= target_rank` passes.
[`architecture.md:208-214`](architecture.md) argues that deriving everything from `issubclass` plus the
stdlib tower avoids "invented knowledge" and a "third, drifting source of truth". This is the tower
inventing a rule on its own — and it is the one decision in the PR where *correct* is a judgement rather
than a comparison against prior behaviour.

**No test covers it.** Changing `source_rank <= target_rank` to `<` — which alters behaviour on this pair
and no other — leaves all 47 tests in `test_graph.py` green. The tested pairs are `int→float`,
`bool→float`, `str→float`, `float→str`, `float→int`: precisely the five numeric rows of
`architecture.md`'s verdict table. The suite asserts what the document decided and is silent where it
did not.

Decide explicitly: is `int → bool` intended? If not, `bool` needs handling before the tower runs.

One adjacent gap, same shape but lower severity: **`Decimal → float` is rejected**, because `Decimal`
registers with `numbers.Number` but not `Real`, so its rank is `None`. The tower decides again — but this
refuses a valid edge and fails loud, where `int → bool` accepts an invalid one and fails silently. No
plugin uses `Decimal`.

Everything else probed behaves correctly: `Fraction`, `complex`, `object`, and every generic alias
(`Optional`, `Union`, `List`, `Tuple`, `Dict`), which skip at
[`graph.py:73-74`](../../packages/coral-app/src/coral_app/graph.py#L73-L74) with no `issubclass` crash
path on Python 3.12.

Reproduce:

```bash
.venv/bin/python -c "
from coral_app.graph import _is_compatible, _numeric_rank
for s, t in [(int,bool),(float,bool),(bool,int),(int,float),(float,int)]:
    print(f'{s.__name__:6} -> {t.__name__:6} {\"accept\" if _is_compatible(s,t) else \"REJECT\":6}'
          f' ranks {_numeric_rank(s)} -> {_numeric_rank(t)}')"
```

### 2. Two documented behaviours rest on one test each

Mutation-tested both new modules (method in
[Resources](#resources-for-reviewing-ai-generated-prs); 13 mutants, 12 killed). The suite is solid:
`nodeports.py` killed all six, including the instance-at-port-0 convention, first-writer-wins precedence,
and the `-> None`-yields-no-output rule. `graph.py` killed five of six — the survivor is finding 1.

Two behaviours, however, are pinned by a single test apiece, and both are ones the docs treat as central:

| behaviour | test coverage | why it matters |
| --- | --- | --- |
| `-1` accepted as "the only output" | 1 test | [`architecture.md:104-117`](architecture.md) devotes a table to it and notes both `0` and `-1` appear on the wire in real graphs |
| ready batches are `sorted()` | 1 test | determinism is a stated design goal in `architecture.md` and `CLAUDE.md`, and the named hook for future concurrent execution. On graphs this small dict order often equals sorted order, so the test may be catching the mutant incidentally rather than by design |

Neither is a defect. Both are single points of failure for behaviour the design leans on.

### 3. `executor.py:64-67` — the kwargs round trip buys nothing, and its comment defends it

```python
# Inputs arrive in port order, which is parameter order, so binding is a zip. The
# signature is the callable's own: `self` is already gone from a bound method.
parameters = list(inspect.signature(target).parameters)
self.results[node_id] = target(**dict(zip(parameters, arguments)))
```

Equivalent, for every callable in the repo:

```python
self.results[node_id] = target(*arguments)
```

`arguments` is already in parameter order — `_input_values()` sorted the edges by `target_input`, which
is port order, which is the order `nodeports` read off the signature. The code labels an already-ordered
list with parameter names, bundles the labels into a dict, and unpacks by label to reach where a
positional call would have put the values.

Three costs, all reproduced:

| cost | evidence |
| --- | --- |
| forbids positional-only parameters | `math.sqrt` is `(x, /)`; a kwargs call raises `TypeError: math.sqrt() takes no keyword arguments`. No installed plugin trips it (all 28 callables checked: no `POSITIONAL_ONLY` / `VAR_POSITIONAL` / `VAR_KEYWORD`), so it is a latent, undocumented constraint on plugin authors. |
| `zip` truncates silently | 3 values into a 2-parameter function returns a result; the extra vanishes. `target(*arguments)` raises `takes 2 positional arguments but 3 were given`. Unreachable today only because graph check 4 runs first. |
| re-introduces `inspect` into the executor | [`architecture.md:68-71`](architecture.md) justifies the whole port-table stage on the grounds that registry and executor derived arity separately, which is "how the two came to disagree about it. One table, no drift." Line 66 is a fresh `inspect.signature` on a plugin callable at run time, re-deriving what `nodeports` already stored. |

Reproduce:

```bash
.venv/bin/python -c "
import inspect, math
from coral_app import build_function_map
add = build_function_map(include=['math'])['add']
p = list(inspect.signature(add).parameters)
print(p, add(**dict(zip(p, [2.0, 3.0]))), add(*[2.0, 3.0]))
print(add(**dict(zip(p, [1, 2, 999]))))   # extra argument silently dropped
try: math.sqrt(**{'x': 4.0})
except TypeError as e: print(e)"
```

**The comment makes this worse, not better.** Sentence 1 establishes that the orders match, therefore the
zip pairs correctly — but *the orders already match* is exactly why the names are unnecessary. It states
the premise that makes the code redundant, then concludes "so binding is a zip" instead of "so a
positional call works." Sentence 2 explains why fetching the signature from the *resolved* target is safe
for all three node kinds, which justifies where the signature comes from, not why one is fetched. Two
confident sentences of justification make the machinery look load-bearing to the next reader; a bare
`**dict(zip(...))` would have invited the question.

If keyword binding is wanted for better tracebacks, read the names off
`self.graph.ports_of(node_id).inputs` rather than calling `inspect` again — noting that a method's port 0
is `("self", cls)` ([`nodeports.py:141`](../../packages/coral-app/src/coral_app/nodeports.py#L141)) and
`_resolve` already stripped it, so that list needs a `[1:]` for methods. Which is more code than
`target(*arguments)`.

### 4. Undocumented ordering invariant between the checks

[`graph.py:264`](../../packages/coral-app/src/coral_app/graph.py#L264) indexes
`.inputs[edge.target_input]`. That is safe **only** because checks 3 and 4 already ran. Reorder the calls
in `__init__` and you get `IndexError` instead of the named `ValueError` the design promises. The coupling
is marked nowhere at the indexing site — only obliquely, by "run in the order listed in `__init__`" above
the check methods.

Same shape as finding 3's `zip` truncation: a distant check is load-bearing for local code that does not
say so. Splitting the chain gives the invariant somewhere to live:

```python
ports = self.ports_of(edge.target)
# target_input is a safe index here: checks 3 and 4 established that this node's
# incoming edges occupy exactly ports 0..n-1 for its type's n inputs.
target_name, target_annotation = ports.inputs[edge.target_input]
```

Not a general request to unchain expressions — there are few of them. But where the hidden intermediate
carries meaning, naming it is worth considering. [`graph.py:158`](../../packages/coral-app/src/coral_app/graph.py#L158)
is the other case: `self.port_table[self.nodes[node_id]["type"]]` conceals *the node's type*, which the
docstring names in prose and the code names nowhere — and it re-indexes `self.nodes` rather than using the
`node()` accessor defined two lines above:

```python
node_type = self.node(node_id)["type"]
return self.port_table[node_type]
```

### 5. A deviation note misdescribes its own effect (C extension classes)

**Not a regression, and no plugin exercises it.** Raised for what it implies about the deviation notes.

[`plan.md:78-80`](plan.md) justifies the `signature(cls)` → `signature(cls.__init__)` fallback as avoiding
a regression of the documented "C extension classes register a constructor, not methods" behaviour. But a
C extension class does not define `__init__` — it inherits `object`'s, whose signature is
`(self, /, *args, **kwargs)`. Strip `self` and the port table records two inputs named `args` and
`kwargs`:

```
signature(datetime)           -> ValueError: no signature found for builtin type
datetime.__init__             -> <slot wrapper '__init__' of 'object' objects>
signature(datetime.__init__)  -> (self, /, *args, **kwargs)
port table inputs             -> [('args', Any), ('kwargs', Any)]
method nodes registered       -> []                                  <- this half is correct
```

The registry then emits a `datetime` node with two `"type": "any"` sockets called `args`/`kwargs`, graph
check 4 would demand two incoming edges for it, and `executor.py:66` raises
`ValueError: no signature found for builtin type` at run time regardless. Same for `range` and `bytes`.

The old code called `signature(cls.__init__)` directly, so it produced the same result — **the PR
preserved this faithfully**. What is wrong is the note: the fallback is doing real work (it stops
`build_port_table` raising on a C extension class) but what it produces is not a usable constructor, and
the note implies it is. So "registers a constructor, not methods" is half true — the *not methods* half
holds exactly.

Why it is in this review at all: `plan.md`'s six deviation notes are the closest thing to a record of
decisions nobody ratified at design time, and one of them describes its own effect incorrectly.

### 6. `parameters` holds strings, not `Parameter` objects

`list()` on a mapping yields its keys, so `parameters` at
[`executor.py:66`](../../packages/coral-app/src/coral_app/executor.py#L66) is `['a', 'b']`, not
`[<Parameter "a">, <Parameter "b">]`. A reader who knows `inspect` stops to check; one who doesn't reads
line 67 wrong. Rename to **`parameter_names`** if the line survives finding 3; it becomes moot if the
line goes.

## Suggested follow-up: fixture-driven validation tests

A recommendation about test design, not a defect. Worth raising because it may have prevented finding 1.

`test_graph.py` builds every graph from inline literals. That was deliberate
([`plan.md`](plan.md) step 4: "all from JSON literals with hand-written port tables, no plugins") and it
keeps the file fast and plugin-agnostic. But it means only the test author can poke at behaviour — a
reviewer or maintainer cannot change an input and see what breaks without editing Python.

The repo already has the convention: `tests/fixtures/valid_workflows/` and
`tests/fixtures/valid_nodes/`, each with a `README.md`, surfaced through `conftest.py` factory fixtures.
Extending it to the rejection cases:

```
tests/fixtures/invalid_workflows/
  dangling-edge-source.json            -> check 1
  unknown-node-type.json               -> check 2
  duplicate-target-input.json          -> check 3
  target-input-out-of-range.json       -> check 3
  missing-input-connection.json        -> check 4
  source-output-out-of-range.json      -> check 5
  minus-one-on-multi-output.json       -> check 5
  output-from-none-returning-node.json -> check 5
  incompatible-edge-type.json          -> check 6
  int-into-bool.json                   -> check 6   <- forces finding 1 to be decided
  cycle-two-nodes.json                 -> check 7
```

One parametrised test loads each file and asserts `pytest.raises(ValueError, match=...)`, plus a
`README.md` mapping file → check → expected message as the sibling directories do. The payoff is a loop a
human can run: open `incompatible-edge-type.json`, change the source node's type from `str` to `float`,
re-run — the test *should* now fail, because the graph became valid. Verification in both directions,
with no source edits.

One constraint: **the port table cannot be a JSON fixture**, since its values are Python type objects
(`float`, `Widget`, `Any`, `type(None)`). So this is a hybrid — graph JSON in files, port table in
`conftest.py`. The module-level `PORT_TABLE` at `test_graph.py:44` is already a de facto fixture; moving
it to `conftest.py` would share it with `test_executor.py` at no cost.

## Non-blocking doc fixes

Neither is a code defect. Both are checkable claims that do not reproduce.

| where | claim | actual |
| --- | --- | --- |
| [`architecture.md:85-93`](architecture.md) | check 6 is *no cycles*, check 7 is *type compatibility* | code runs types then ordering ([`graph.py:132-134`](../../packages/coral-app/src/coral_app/graph.py#L132-L134)); `CLAUDE.md` and [`plan.md`](plan.md) agree with the code, `architecture.md` alone disagrees |
| [`architecture.md:206`](architecture.md), [`plan.md:166`](plan.md) | "all 144 edges" across six fixtures + the phiflow example are `Any`-involved or exact match | 6+5+3+31+27+45+31 = **148**. The conclusion ("no existing graph is affected") may still hold; it was not established by the count presented |

**The one question to ask the author:** why does check 6 run before the cycle check, and why does
`architecture.md` say the opposite? The answer indicates how much of this PR was read as opposed to
generated.

## Resources for reviewing AI-generated PRs

| resource | use it for |
| --- | --- |
| [Google's Code Review Developer Guide](https://google.github.io/eng-practices/review/) | Free and canonical. Its "what to look for" ordering — design first, then complexity, then tests — is the right sequence for a PR this shape. |
| Addy Osmani, *Beyond Vibe Coding* (O'Reilly, 2025) | The only book aimed squarely at this. Read Ch 5 (p.97–107), Ch 8's "Code Review Strategies" (p.165–166), Ch 10's "Challenges and Limitations" (p.199–201). Skip Ch 1–2, 6–7, 11 — tool tours and speculation. |
| Fowler, *Refactoring* (2nd ed.) | Judging whether a behaviour-preserving change preserved behaviour. Ch 2 on when *not* to refactor frames the new-rejections risk. |
| Feathers, *Working Effectively with Legacy Code* | Characterization tests. This PR already uses the technique (golden registry files, `test_characterization.py`); the book tells you how to distinguish a real one from a decorative one. |
| [Simon Willison on AI-assisted programming](https://simonwillison.net/tags/ai-assisted-programming/) | The most useful current writing on taking responsibility for LLM output. |
| METR 2025 RCT | Measured a slowdown for experienced developers where participants predicted a speedup. Calibration against one's own sense of how fast this went. |

### Mutation testing

Coverage says which lines ran, not whether a wrong answer would be noticed. AI-written tests often assert
the implementation back at itself, so break the code deliberately and see whether the suite complains.
Each mutant asks one question:

| change | asks |
| --- | --- |
| `source_rank <= target_rank` → `<` | is numeric widening actually pinned? |
| `(None, 0, -1)` → `(None, 0)` | does anything test `-1` as "the only output"? |
| `inputs = [("self", cls)]` → `[]` | is the instance-at-port-0 convention tested? |

Edit one line, run the single relevant file (`pytest tests/test_graph.py -q` — 0.05s, no plugins), then
`git checkout --` it before trying the next.

Reading the result:

- **tests fail** — the behaviour is pinned.
- **tests pass** — the line runs but nothing asserts anything depending on it. A gap.
- **half the suite fails** — over-coupled; one change should not cascade.
- **no input can tell the two versions apart** — an *equivalent mutant*, so surviving proves nothing.
  Check this before reporting a gap: finding 1's survivor was checked, and `int → bool` is the only
  distinguishing pair.

Pick mutants from the design decisions, not mechanically. `mutmut` and `cosmic-ray` return a percentage
over hundreds of generated mutations — useful for CI trends, wrong instrument for a review.

### Concepts worth naming, in general and for this PR

- **Coherent incorrectness** (Osmani p.199). Sequential autonomous decisions do not produce one flawed
  function — they produce an internally consistent architecture built on the first misunderstanding.
  *Here:* the choice to derive compatibility from the `numbers` tower propagated into `graph.py`, into
  both `architecture.md` and `CLAUDE.md`, and into the shape of the tests. Everything corroborates
  everything else — and the pair it gets wrong, `int → bool`, appears in none of them. `architecture.md`
  and `CLAUDE.md` state only `bool → int`; the only `bool` case in a compatibility test is `bool → float`,
  and neither direction between `int` and `bool` is tested anywhere. Coherence is what let finding 1
  through, not what would have caught it.
- **Accidental vs essential complexity** (p.68, after Brooks). AI is strong on the mechanical, weak on
  the inherent difficulty of the problem. *Here:* consolidating arity derivation is accidental — skim it,
  the golden files verify it. Deciding what type compatibility *means* is essential — no amount of
  passing tests settles it.
- **The majority solution effect** (p.99). AI produces the answer most represented in its training data,
  right in general but not necessarily for your case; "the tailoring is your job." *Here:* the `numbers`
  tower is the idiomatic Python answer to "express numeric widening." Whether it is the right answer for
  coral graph edges is a separate question the plan never asks — finding 1 is what that costs.
- **Generator/reviewer asymmetry, and the review bottleneck** (p.194, p.200). Agents shift human effort
  from writing to vetting, but their PRs arrive complete rather than incrementally, so the reviewer must
  reverse-engineer the reasoning from the code — Osmani's phrase is "archaeological expedition." *Here:*
  +2784 / −387 at the point of review, across two new modules and four markdown files, all at once.
- **Docstring-vs-code drift is a named, expected failure mode** (p.101): "a function docstring saying one
  thing but the code doing another (if it revised the logic but not the comment)." *Here:* both entries
  in [Non-blocking doc fixes](#non-blocking-doc-fixes), finding 3's comment, and finding 5 — a deviation
  note describing an effect its own code does not have. Four instances in one PR.
- **Don't merge code you don't understand** (p.78), and its reviewer half (p.165): if the author cannot
  explain a line and reaches for "the AI did it," that is the red flag. *Here:* that is what the one
  question above is for.
- **The overconfidence finding** (p.137, p.154). Developers using AI assistance were *more* confident in
  their code's security even when it was objectively less secure. Worth holding next to the confident,
  table-filled prose in `architecture.md`.

Tone note: these findings are about AI-generated artifacts, not about the author. The register that works
is p.166's — "this part seems to have an issue, likely an oversight from the AI suggestion; let's fix it."
