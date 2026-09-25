# Plan: a registered class is rendered as its own type in `node_types.json`

Fixes [#44](https://github.com/2listic/coral-python/issues/44) and
[#34](https://github.com/2listic/coral-python/issues/34). This file is self-contained: it holds the
context, the decisions taken with the user, and the steps. An implementer with no memory of the
discussion must be able to execute it from here alone.

Tick a box (`- [x]`) as soon as the item is done — and a **Check** box only after the check has
actually been run and passed.

---

## 0. Working rules (the user's, non-negotiable)

1. **Never modify a file without showing the exact diff first and getting an explicit go-ahead.**
   Every edit — code, tests, docs, goldens, and ticking boxes in this plan. Approval of one diff never
   extends to another.
2. **One step at a time.** After each *step* (not substep): run its checks, report, and **stop**.
   Wait for the user before the next step.
3. **Never commit.** The user commits.
4. **Open decisions (§4) are asked one at a time**, at the start of the step that needs them, with a
   recommendation. Never decide them alone.
5. Brief, direct answers; conclusion first.
6. Every new test's docstring uses the `GIVEN / WHEN / THEN` structure (see existing tests).
7. No issue, PR, step or decision numbers in code, docstrings or comments (`CLAUDE.md`, Key
   Constraints). Keep the reasoning, drop the citation.
8. Vocabulary: **front end** = dealiiX-platform (TypeScript); **back end** = coral-python, or the
   C++ `2listic/coral`. The word "editor" is banned — it is ambiguous (the C++ repo's local directory
   is called `coral-editor`).
9. Under `coral-core/tests` and `coral-app/tests`, never write a string literal equal to a plugin
   name (`"math"`, `"string"`, `"phiflow"`, `"pypde"`) — not even in a docstring: the invariants
   (`tests/invariants/test_source_rules.py`) fail on it.

Checks available at any time (no approval needed):

```bash
uv run pytest -m "not slow" -q                 # fast lane, ~1s
uv run pytest -q                               # everything (slow ~1 min; includes the network test)
uv run ruff check coral-core coral-app plugins tests
uv run ruff format --check coral-core coral-app plugins tests
```

---

## 1. Context

### 1.1 What the registry is
`coral register` writes `node_types.json`, the file the **front end** reads to build its node palette
and to validate edges. The back end never reads it: graph validation and execution use the Python
annotations held in the port table (`coral_app/nodeports.py`). Code:
`coral-app/src/coral_app/registry.py`.

Every socket is an `arguments[]` entry `{"connection_type", "type", "name"}`; its `"type"` string
comes from `registry.py:python_type_to_string(annotation)`.

### 1.2 The defect
`python_type_to_string` knows nine names (`TYPE_NAMES` in `coral_app/primitives.py`: `int`, `float`,
`str`, `bool`, `any`, `none` + `list`, `set`, `dict`) and returns `"any"` for **everything else** —
including every plugin class. Example today:

```json
"Calculator.add_to_value": {"arguments": [
  {"connection_type": "input",  "type": "any",   "name": "self"},
  {"connection_type": "input",  "type": "float", "name": "amount"},
  {"connection_type": "output", "type": "float", "name": ""}], ...}
```

Class-typed sockets rendered `"any"` today (measured on the port table):

| plugin | sockets |
| --- | --- |
| math | 3 × `self` (`Calculator`) |
| string | 2 × `self` (`StringProcessor`) |
| phiflow | 5 × `self` (one per wrapper class's method) |
| pypde | 1 × `self` (`PyPDEDiffusionPDE.solve`); 5 inputs (`PyPDEScalarField.grid`, `PyPDEPlotTracker.movie`, `PyPDEDiffusionPDE.solve`'s `state` / `storage` / `plot`); 1 output (`PyPDEDiffusionPDE.solve` → `PyPDEScalarField`) |
| **total** | **17** |

Specimen (`coral-app/tests/specimen.py`, which the format golden is generated from): 7 × `self` —
`Accumulator.add`, `Accumulator.total`, `Gauge.label`, `PreciseAccumulator.add` / `.total` /
`.rounded`, `Tally.bump`.

Constructors are **not** affected: they are written `outputs: [-1]` with no output argument, and the
front end types that output itself (§1.3).

### 1.3 How the front end validates an edge (dealiiX-platform `main`, read from source)
- `src/lib/types/nodeTypes.ts:111` `isTypeCompatible(source, target)`: `"any"` on **either** side →
  accept; `bool → int → float` widening → accept; otherwise **exact string match**.
- A constructor's output (`outputs: [-1]`) is typed `base ?? type`
  (`src/lib/utils/canvasNodeUtils.ts:145` and `:405`). So `Calculator`'s output is `"Calculator"`.
- The rule is used in all three paths: drawing an edge (`connectionsValidation.ts:74`), loading a
  graph (`graphParser.ts:269`), suggestions (`canvasNodeUtils.ts:190`, `:282`).
- Consequence today: with `self` typed `"any"`, any source is accepted into an instance port — class
  wiring is not checked in the front end at all.

### 1.4 How the C++ back end does it (`2listic/coral`, read from source)
- One function, `detail::hash<T>()`, names both a type's node entry and every socket of that type
  (`core/include/coral.h:1425`, `:1455`). A method's instance port is therefore the class's node type
  string — what this plan does for Python.
- A derived type is registered with `register_derived_type<B, T>()`; its entry carries
  `"base": "<B>"` (`coral.h:748`). The front end then types its constructor's output as `B`.

### 1.5 Subclasses: what works where
Example: `class Sphere(Shape)`, both registered; `Sphere.volume` has `self: Sphere`.

| edge | Python back end | C++ back end | front end, no `base` | front end, with `base` |
| --- | --- | --- | --- | --- |
| `Sphere` → port expecting `Shape` | ✓ (`issubclass`, check 8) | ✓ (one level) | ✗ | ✓ |
| `Sphere` → port expecting `Sphere` | ✓ | ✓ | ✓ | ✗ |

The front end keeps one type name per output, so it cannot satisfy both rows. The fix is on its side
— **dealiiX-platform#224** (posted): keep the output as its own type and accept a target that is an
ancestor, walking `base`. The C++ limitations (one level; no edge type check at load) are
**2listic/coral#63** (posted). Neither is part of this plan.

Python registers **every** public method of a class, inherited ones included (`nodeports.py:115`,
`dir(cls)`), so `Sphere.volume` and `Sphere.area` always exist with `self: "Sphere"`.

### 1.6 Files involved
| file | role |
| --- | --- |
| `coral-app/src/coral_app/registry.py` | renders the port table into the file; owns `python_type_to_string` |
| `coral-app/src/coral_app/nodeports.py` | port table; `build_port_table` refuses duplicate node types (`put`) |
| `coral-app/src/coral_app/executor.py:64` | calls `build_port_table(self.function_map, self.class_map, self.primitives_map)` |
| `coral-app/src/coral_app/primitives.py` | `PRIMITIVES_MAP`, `COLLECTION_TYPES`, `TYPE_NAMES` (all re-exported by `coral_app`) |
| `coral-app/src/coral_app/errors.py` | `DuplicateNodeTypeError` |
| `coral-app/tests/specimen.py` | designed plugin surface; `PreciseAccumulator(Accumulator)` is the ready-made subclass; clash plugins + `PLUGINS` map |
| `coral-app/tests/conftest.py` | `specimen_plugins` fixture (patches `coral_app.load`), `write_graph` |
| `coral-app/tests/test_registry.py` | format tests + `TestFormatGolden` |
| `coral-app/tests/test_nodeports.py` | port-table tests (duplicate-name tests ~l.330–372) |
| `coral-app/tests/test_executor.py` | executor tests (`TestConstruction`) |
| `coral-app/tests/golden/node_types.format.json` | format golden (specimen + rival) |
| `plugins/coral-*/tests/system/golden/node_types.*.json` | the four plugin goldens |
| `CLAUDE.md`, `docs/ONBOARDING.md` | documentation |

---

## 2. Decisions (taken with the user)

| # | question | decision | why |
| --- | --- | --- | --- |
| D1 | which classes get a name? | only classes in `class_map` (what plugins return from `get_classes()`), written as their **`class_map` key** | the same string the front end uses for the constructor's output, so the two match by construction; every type written names an existing node type. Today every key equals `cls.__name__` (13/13) |
| D2 | a class not in `class_map` | stays `"any"` — including a class of an **unselected** plugin | no node could produce it; `"any"` causes no false refusal in the front end |
| D3 | wrapped annotations: `List[X]`, `Optional[X]`, unions, `List[int]` | **unchanged**, still `"any"` | the user wants precise generic types (`List[int]` stays `List[int]`; heterogeneous = `List[Any]`) but in a **separate issue**: it needs a canonical spelling and new compatibility rules in the front end and in check 8. Lists/sets/dicts must not break now |
| D4 | subclasses (Liskov) | a subclass is written as its own name; its **constructor entry** carries `"base": "<key of the nearest registered ancestor>"` | same format as C++; lets the front end walk the chain once dealiiX-platform#224 lands |
| D5 | "nearest registered ancestor" | the first class in `cls.__mro__[1:]` that is in `class_map`; no `base` key when there is none | covers multi-level chains (`Ball → Sphere → Shape`: `Ball`'s base is `Sphere`) |
| D6 | multiple inheritance | `base` names only the first registered ancestor in MRO order | one string, as in C++. Several parents = a later extension (separate issue) |
| D7 | a class or function named `list` / `set` / `dict` | refused with `DuplicateNodeTypeError`, under **both** `register` and `run` | otherwise its socket `"list"` is indistinguishable from a real list in the front end |
| D8 | `register` must refuse what `run` refuses | `generate_registry` passes the primitives to `build_port_table` | before, `coral register` accepted a class named `int`, which `coral run` refused. **Implemented** (step 0) |
| D9 | how `python_type_to_string` gets the lookup | optional parameter `class_names: Mapping[type, str] = None`; `generate_registry` builds it once from `class_map` and threads it down | keeps the function pure; calls without it behave as today. Rendered names in the port table would put format knowledge in `nodeports.py`, which the module split forbids |

**State today**: none of the 13 registered plugin classes has a registered ancestor, so **no plugin
golden gains a `base`**. Only the specimen (`PreciseAccumulator`) does. Nothing breaks.

---

## 3. What does not change
- Back-end behaviour: graph checks 1–9, the executor, the port table's contents.
- Every non-class annotation: primitives, collections, `Any`, missing annotations, generics.
- Constructors keep `outputs: [-1]` with no output argument.
- The order of existing entry keys; `base`, when present, is added (position: O3).

---

## 4. Open decisions (ask the user at the start of the step that needs them)

| # | step | question | recommendation |
| --- | --- | --- | --- |
| O1 | 1 | how `build_port_table` learns the collection names | a parameter `reserved: Iterable[str] = ()`, passed `COLLECTION_TYPES` by both callers (as `primitives` is passed, not imported) |
| O2 | 2 | one class registered under two keys (`{"A": X, "B": X}`) makes `class → name` ambiguous | raise `ValueError` naming both keys, in `generate_registry` |
| O3 | 3 | where `"base"` goes in the entry | last, after `"type"` (existing bytes do not move) |

---

## 5. Steps

### Step 0 — `register` refuses what `run` refuses (D8) — DONE, committed in `65b75b2`

- [x] 0.1 `registry.py` `generate_registry`: `build_port_table(..., primitives={name: PRIMITIVES_MAP[name] for name in primitives})`; comment extended.
- [x] 0.2 `test_registry.py`: import `DuplicateNodeTypeError`; new test
      `TestPrimitiveEntries::test_a_class_named_after_a_primitive_is_refused`.
- [x] Step checks: fast lane green (546 passed) · ruff clean
- [x] STOP — reported to the user

### Step 1 — refuse node types named `list` / `set` / `dict` (D7)

- [x] O1 asked and decided: `nodeports.py` imports `COLLECTION_TYPES` and checks it itself — no
      parameter. The rule holds for every caller, so no caller can forget it (the step 0 bug).
- [x] 1.1 `nodeports.py` `build_port_table`: import `COLLECTION_TYPES` from `coral_app.primitives`;
      in `put`, a `node_type` in `COLLECTION_TYPES` raises
      `DuplicateNodeTypeError(f"node type {node_type!r} is a reserved type name")`; docstring
      (`Raises`) updated.
  - [x] Check: `build_port_table(class_map={"list": X})` raises.
- [x] 1.2 (no code change: `generate_registry` goes through `build_port_table`)
  - [x] Check: `generate_registry(dict(BUILTIN_FUNCTIONS), list(PRIMITIVES_MAP), {"list": X})` raises
        `DuplicateNodeTypeError`.
- [x] 1.3 `specimen.py`: add `CollectionClashPlugin` (`get_classes` → `{"list": Tally}`,
      `get_functions` → `{}`), `COLLECTION_CLASH = "collection-clash"`; add both to `__all__` and to
      `PLUGINS`; update the module docstring (the plugin count and the list of clash plugins).
  - [x] Check: `uv run pytest tests -q` (invariants) green.
- [x] 1.4 (no code change: the executor goes through `build_port_table`)
  - [x] Check: `WorkflowExecutor(path, plugins=[COLLECTION_CLASH])` raises `DuplicateNodeTypeError`
        at construction.
- [x] 1.5 Tests (GWT docstrings):
  - [x] `test_nodeports.py`, duplicate-name class (~l.330): a class keyed `list` raises; a function
        keyed `dict` raises; a method key (`Widget.list`-style) is not affected.
  - [x] `test_registry.py`: a class keyed `set` is refused by `generate_registry`.
  - [x] `test_executor.py` `TestConstruction`: `WorkflowExecutor(path, plugins=[COLLECTION_CLASH])`
        raises `DuplicateNodeTypeError` (fixtures: `write_graph`, `specimen_plugins`; any valid
        graph, e.g. `graph({"0": {"type": "int", "value": 1}})` — the port table is built, and
        refused, before the graph is read).
  - [x] Check: each new test fails without 1.1, and passes with it.
- [x] Step checks: fast lane green · ruff check clean · ruff format clean
- [x] STOP — reported to the user, go-ahead received

### Step 2 — a registered class renders as its key (D1, D2, D3, D9)

- [x] O2 asked and decided: refused with `DuplicateNodeTypeError` naming both keys, in
      `build_port_table` — every map passes through it, so `register` and `run` both refuse.
- [x] 2.0 `nodeports.py` `build_port_table`: the O2 refusal; the two tests that register `Widget`
      under two keys (`test_methods_of_lists_one_class`,
      `test_a_constructor_wins_over_a_method_of_the_same_key`) get a class of their own.
- [x] 2.1 `registry.py` `python_type_to_string(py_type, class_names: Mapping[type, str] = None)`
      (add `Mapping` to the `typing` import):
      after the `TYPE_NAMES` lookup, `if class_names and py_type in class_names: return
      class_names[py_type]`; final fallback stays `"any"`. Docstring rewritten: the three sources
      (primitives, collections, registered classes); anything else, generics included, is `"any"`.
  - [x] Check: `python_type_to_string(X, {X: "X"}) == "X"`; `python_type_to_string(X) == "any"`;
        `python_type_to_string(List[X], {X: "X"}) == "any"`.
- [x] 2.2 Thread `class_names` through `_create_input_argument`, `_create_output_argument`,
      `_number_inputs`, `_number_outputs`, `_add_function_node`, `_add_constructor`, `_add_methods`.
  - [x] Check: `grep -n "python_type_to_string(" coral-app/src/coral_app/registry.py` shows no call
        without `class_names`.
- [x] 2.3 `generate_registry`: build `class_names = {cls: name for name, cls in (class_map or {}).items()}`
      once; pass it down. Docstring updated (class sockets carry the class key).
  - [x] Check: on the specimen, `Accumulator.add`'s `self` is `"Accumulator"`.
- [x] 2.4 Existing tests whose statement becomes false:
  - [x] `test_registry.py::TestConstructorAndMethodEntries::test_a_method_takes_the_instance_at_port_zero`:
        `self` is `"Accumulator"`; docstring rewritten (it says the format has no name for a class).
  - [x] `test_registry.py::TestPythonTypeToString::test_an_unknown_class_is_any`: assertion kept;
        docstring → "a class not registered by any selected plugin".
- [x] 2.5 New tests in `test_registry.py` (GWT):
  - [x] a registered class renders as its key.
  - [x] a registered class inside `List[...]` / `Optional[...]` stays `"any"`.
  - [x] a class registered under a key different from its `__name__` renders as the **key**.
  - [x] a subclass's inherited method has `self` = the **subclass's** key
        (`PreciseAccumulator.add` → `"PreciseAccumulator"`).
  - [x] a parameter annotated with a registered class carries its key (local classes via
        `generate_registry`; do not grow the specimen for it).
  - [x] a return annotated with a registered class carries its key (same).
  - [x] O2's behaviour (in `test_nodeports.py`, where the rule lives).
- [x] Step checks: fast lane — the **only** failures are the five golden byte tests (format + four
      plugins; fixed in step 4) · ruff check clean · ruff format clean
- [x] STOP — reported to the user, go-ahead received

### Step 3 — emit `base` (D4, D5, D6)

- [x] O3 asked and decided: `"base"` goes last, after `"type"` — existing bytes do not move.
- [x] 3.1 `registry.py` `_add_constructor`: receive the class (`class_map[class_name]`) and
      `class_names`; `base = next((class_names[c] for c in cls.__mro__[1:] if c in class_names), None)`;
      if not `None`, add `"base": base` at the O3 position. Docstring: what `base` is, that the front
      end reads it.
  - [x] Check: specimen `PreciseAccumulator` has `"base": "Accumulator"`; `Accumulator`, `Gauge`,
        `Tally` have no `base` key.
- [x] 3.2 Tests in `test_registry.py` (GWT), local classes where the specimen lacks the shape:
  - [x] `PreciseAccumulator` carries `"base": "Accumulator"`.
  - [x] a class with no registered ancestor has no `base` key (not `null`, not `""`).
  - [x] three levels `C(B(A))`, all registered: `C`'s base is `B`, `B`'s is `A`.
  - [x] unregistered middle, `C(B(A))` with only `A` and `C` registered: `C`'s base is `A`.
  - [x] multiple inheritance `D(A, B)`, both registered: `base` is `A` (MRO order).
  - [x] `base` is the **key**, not `__name__`.
  - [x] method entries never carry `base`.
- [x] Step checks: fast lane — again only the five golden byte tests fail · ruff check clean · ruff
      format clean
- [ ] STOP — reported to the user, go-ahead received

### Step 4 — regenerate the goldens

Run from the workspace root. Show each golden's `git diff` to the user before keeping it. Both
commands were verified to reproduce the current goldens byte-for-byte before any change.

- [x] 4.1 Format golden:
      ```bash
      uv run python -c "import sys; sys.path.insert(0, 'coral-app/tests'); import coral_app, specimen; coral_app.load = lambda n: specimen.PLUGINS[n](); from coral_app.registry import save_registry_to_file; save_registry_to_file('coral-app/tests/golden/node_types.format.json', plugins=[specimen.SPECIMEN, specimen.RIVAL])"
      ```
  - [x] Check: the diff is exactly the 7 specimen `self` sockets `"any"` → class key, plus one
        `"base": "Accumulator"` on `PreciseAccumulator`. Nothing else.
- [x] 4.2 Plugin goldens:
      ```bash
      uv run coral -p math    register --output=plugins/coral-math/tests/system/golden/node_types.math.json
      uv run coral -p string  register --output=plugins/coral-string/tests/system/golden/node_types.string.json
      uv run coral -p phiflow register --output=plugins/coral-phiflow/tests/system/golden/node_types.phiflow.json
      uv run coral -p pypde   register --output=plugins/coral-pypde/tests/system/golden/node_types.pypde.json
      ```
  - [x] Check: the changed `"type"` lines are exactly the 17 of §1.2 (math 3 / string 2 / phiflow 5 /
        pypde 7), all `"any"` → a class key; **no** `base` anywhere; no other line changes. Anything
        else is a bug: stop and report.
- [x] 4.3 Plugin tests that read the golden and asserted the old `"any"`:
      `coral-string` `test_the_method_nodes_carry_the_instance_at_port_zero`;
      `coral-pypde` `test_a_wrapper_typed_socket_renders_any` (renamed
      `test_a_wrapper_typed_socket_carries_the_wrapper_key`).
- [x] Step checks: `uv run pytest -q` (full suite, slow included) green · ruff clean
- [ ] STOP — reported to the user, go-ahead received

### Step 5 — documentation

Every wording is shown as a diff and approved by the user.

- [x] 5.1 `CLAUDE.md`:
  - [x] *Registry Files* (~l.378): a registered class's socket `type` is its class key; constructor
        entries may carry `base` (nearest registered ancestor); front-end dependency
        (dealiiX-platform#224); multiple inheritance = first parent only.
  - [x] *Key Constraints → Type system*: registered classes as the third source of socket type names.
  - [x] *Type Hint Requirements* (~l.896): a class annotation renders as its key only if registered,
        else `"any"`; generics stay `"any"`.
  - [x] `grep -n '"any"' CLAUDE.md`: any other statement made false is listed to the user.
        Also extended (approved): the `nodeports.py` description and Data Flow stage 3 now name
        the two new refusals.
- [x] 5.2 `docs/ONBOARDING.md`: l.175–182; l.500–506 ("Richer type system", now partly done);
      l.630–637 ("Lossy type system", already stale: says six types).
- [x] 5.3 `README.md`, `tests/README.md`: grep for statements about class sockets; report (probably
      none).
      Result: nothing to change.
- [x] Step checks: every wording approved · `uv run pytest -q tests` green
- [ ] STOP — reported to the user, go-ahead received

### Step 6 — final verification and handover

- [ ] 6.1 `uv run pytest -q` all green; `uv run pre-commit run --all-files` clean.
- [ ] 6.2 `git diff --stat main...` (plus `git status` for uncommitted work): only the files of
      §1.6 and this plan changed.
- [ ] 6.3 Summary to the user: what changed, the 17 + 7 socket diffs, the specimen's `base`. **No
      commit.**
- [ ] 6.4 Draft (do not post) the two follow-up issues of §6 for the user to review.

---

## 6. Out of scope — issues to open (drafts, user reviews before posting)

1. **Precise generic socket types**: `List[int]` stays `List[int]`, `Optional[X]` stays
   `Optional[X]`, heterogeneous lists = `List[Any]`. Needs: one canonical spelling (`typing.List[int]`
   vs `list[int]`; `Optional[X]` = `Union[X, None]` = `X | None`), compatibility rules
   (`list` ↔ `List[int]`, `X` → `Optional[X]`, `List[int]` → `List[Any]`) in the front end **and** in
   check 8, and the builtin collection nodes' annotations.
2. **Multiple inheritance in the registry**: `base` holds one parent; a class with two registered
   parents cannot be accepted into ports typed with its second parent.

## 7. External issues already posted (context, not work)
- dealiiX-platform#224 — front end cannot validate edges between a derived type and its own type.
- 2listic/coral#63 — C++: multi-level inheritance cannot be registered; edge types are not checked
  when a network is loaded.
- dealiiX-platform#215 — `"any"` wildcard on both sides + numeric widening: **already landed** on
  `main`.
