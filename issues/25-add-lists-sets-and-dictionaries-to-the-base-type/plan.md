# Plan: lists, sets and dictionaries as fundamental types

Implements [`desiderata.md`](desiderata.md). That file holds the requirements; the decisions reached
in discussion are recorded below, then the steps.

## Decisions

| # | question | decision | why |
| --- | --- | --- | --- |
| 1 | where do the types live? | **the host**, not a plugin — no new distribution | shared operations belong to everyone; a plugin would have to be installed to get them |
| 2 | operations as functions or as wrapper classes? | **host functions** over bare `list`/`set`/`dict` | a wrapper `List` is not a `list`, so every plugin boundary would cost a conversion node, in the direction that matters (a plugin *producing* a list) |
| — | why not register the real `list`/`set`/`dict` classes? | impossible | `inspect.signature(list)` is `(iterable=(), /)` → one mandatory input port, so check 4 forbids an empty-list constructor node; `_public_method_names(list)` is `[]` (C extension); `list.append` mutates and returns `None` → no output port |
| 3 | can a collection primitive carry a literal? | **no — empty only** | JSON cannot express an object, so a literal would only ever serve scalars, while the `*_new` + `*_append` chain is mandatory anyway. One way to build a collection. Widening this later is backwards compatible |
| 4 | node type names | **underscored**: `list_new`, `list_append`, … | in `node_types.json` a dot already means a module (`math.sqrt`) or a class (`Calculator.add_to_value`); `list.append` is valid Python for a real builtin method with *different* semantics (mutates, returns `None`), so the name would assert something false. Follows the `phiflow_*` precedent |
| 5 | operations | create / add / extract / inspect, per type | see the table in step 2 |
| 6 | removal | one index/key-based op per type, fail loud | `list_remove` would be ambiguous (Python removes by *value*), hence `list_remove_at` |
| 7 | may a plugin shadow a builtin name? | **no — builtins always win** | the existing "later wins" rule resolves a collision between two *plugins* (`print_result` in math and string), where neither has precedence. A builtin is a host guarantee: a plugin silently redefining `list_append` for every graph on the platform would be undebuggable from the graph |

Semantics common to all of them:

- **Pure.** Every operation returns a *new* collection. A node's result is shared by every downstream
  consumer, so in-place mutation would make the graph's outcome depend on execution order.
- **Fail loud.** A missing index or key raises (`IndexError` / `KeyError`); no `None` fallback, and no
  default arguments — check 4 requires every port to be wired, so a default would be unreachable.
- **No element typing.** Annotations are the bare `list` / `set` / `dict`; elements are `Any`. A
  generic alias such as `List[int]` would make graph check 6 skip the edge entirely.

## ⚠ Unresolved before step 1 — found in the coherency review

**Decisions 3 and 5 collide: the `list` primitive node and `list_new()` do the same thing.** With
decision 3 (empty-only), a `{"type": "list", "value": ""}` node reliably yields `[]` — which is
exactly what `list_new()` yields. Two node types, identical behaviour, contradicting decision 3's own
stated goal of *one* way to build a collection. Three ways out:

| | what | consequence |
| --- | --- | --- |
| **(i)** | keep both | editor shows `list` (primitive) *and* `list_new` (function) for the same result |
| **(ii)** | drop `*_new`, the primitive node is the creator | 12 nodes, but the creator depends on a `value` field being empty — the fragility that motivated an explicit creator |
| **(iii)** | `list`/`set`/`dict` become **type names only, not node types** | recommended — see below |

**(iii) in detail:** do *not* add them to `PRIMITIVES_MAP`. Add a separate map in `primitives.py`
consumed only by `registry.py`'s reverse lookup, so `python_type_to_string` still renders `"list"`
instead of `"any"`. Then:

- sockets are typed `list`/`set`/`dict` — the whole point of step 1 is preserved;
- no collection primitive node exists, so `list_new()` is the only creator, and graph check 2 rejects
  `{"type": "list"}` as an unknown type — "one way" enforced, not just intended;
- **step 1 collapses to a few lines**: no `EMPTY_PRIMITIVES`, no `_convert` branch, no empty-value
  semantics, no `ValueError`, and `executor.py` is not touched at all;
- cost: `PRIMITIVES_MAP` stops being "every type name the registry can print", a split that must be
  documented in `primitives.py`.

Step 1 below is written for (i)/(ii). **If (iii) is chosen, step 1 is replaced by the paragraph
above** and the primitive-node substeps of steps 1, 4 and 5 drop out.

## Steps

Bottom-up: the types first, then the operations, then the host wiring, then the two consumers
(registry, graph), then end-to-end. Every step ends with the whole suite green.

New test docstrings use GIVEN/WHEN/THEN. **None of the new tests may be tagged
`@pytest.mark.<plugin>`** — builtins exist with zero plugins installed, and the tests must assert
exactly that.

### 1. The three types — `packages/coral-app/src/coral_app/primitives.py`

- [ ] Append `"list": list`, `"set": set`, `"dict": dict` to `PRIMITIVES_MAP`, **after** the existing
      entries — the key order of `node_types.json` is part of the platform contract, so existing keys
      must keep their positions.
- [ ] Add `EMPTY_PRIMITIVES = frozenset({"list", "set", "dict"})`: the primitive types whose node
      ignores its `value` and always yields an empty collection (decision 3). Document *why* the name
      list lives here and not in `executor.py`: `primitives.py` owns the type table.
- [ ] `executor.py::_convert` — one branch, before the existing casts:
      `if node["type"] in EMPTY_PRIMITIVES: return converter()` (i.e. `list()` / `set()` / `dict()`).
  - [ ] Reject a non-empty `value` with `ValueError` naming the node type, rather than silently
        discarding data. `""` (what `register` emits), `[]`, `{}`, `None` and an absent key are all
        accepted as "empty".
  - [ ] Do **not** reach for `json.loads` — `executor.py` is deliberately free of `json`.
- [ ] Tests in `tests/test_plugins.py::TestPrimitivesMap` (mirroring the existing style) and
      `tests/test_executor.py`:
  - [ ] `PRIMITIVES_MAP` contains `list`/`set`/`dict` mapped to the real Python types.
  - [ ] a `list` / `set` / `dict` primitive node with `value: ""` executes to `[]` / `set()` / `{}`.
  - [ ] a `list` primitive node with `value: "[1,2,3]"` raises `ValueError` — the silent-garbage case
        (`list("[1,2,3]")` is a list of 7 characters) must be impossible.
- [ ] Check `python_type_to_string` needs no change: `_REVERSE_PRIMITIVES_MAP` is rebuilt from
      `PRIMITIVES_MAP`, so a `list` annotation now renders as `"list"` instead of `"any"`.

### 2. The operations — new `packages/coral-app/src/coral_app/builtin_nodes.py`

One job: the host's own function surface. Same role for callables that `primitives.py` has for types.
Imports nothing from `coral_app`.

- [ ] Module docstring: these are node types available under **any** `-p` selection and even with no
      plugin installed at all, exactly like primitives; and the purity/fail-loud contract above.
      (Don't write "including `-p ''`" — an empty `-p` means *all* installed plugins, not none.)
- [ ] The 15 functions:

| | create | add | extract | inspect | remove |
| --- | --- | --- | --- | --- | --- |
| **list** | `list_new() -> list` | `list_append(lst: list, item: Any) -> list` | `list_get(lst: list, index: int) -> Any` | `list_size(lst: list) -> int` | `list_remove_at(lst: list, index: int) -> list` |
| **set** | `set_new() -> set` | `set_add(s: set, item: Any) -> set` | `set_to_list(s: set) -> list` | `set_size(s: set) -> int` | `set_remove(s: set, item: Any) -> set` |
| **dict** | `dict_new() -> dict` | `dict_set(d: dict, key: Any, value: Any) -> dict` | `dict_get(d: dict, key: Any) -> Any` | `dict_size(d: dict) -> int` | `dict_delete(d: dict, key: Any) -> dict` |

- [ ] Implementations — copy then operate, so the fail-loud behaviour is the builtin's own:
  - [ ] `list_remove_at`: `out = list(lst); del out[index]; return out` (slicing would silently
        no-op on an out-of-range index; `del` raises `IndexError`).
  - [ ] `set_remove`: `out = set(s); out.remove(item); return out` (`remove`, not `discard` —
        `KeyError` on absent).
  - [ ] `dict_delete`: `out = dict(d); del out[key]; return out`.
  - [ ] `list_append`: `[*lst, item]`; `set_add`: `s | {item}`; `dict_set`: `{**d, key: value}`.
  - [ ] `set_to_list`: `sorted(s)` — a `set` of strings iterates in a different order **between
        runs** (hash randomisation), which would make a graph non-reproducible. Document that this
        raises `TypeError` on mutually incomparable elements, and that that is the accepted price.
  - [ ] No `print()` calls (unlike the plugins' functions): the executor already reports each node.
- [ ] `BUILTIN_FUNCTIONS: Dict[str, Callable]` mapping each node type name to its function, in the
      table's order (list, set, dict — create/add/extract/inspect/remove within each).
- [ ] No `BUILTIN_CLASSES` — nothing needs it; do not add an unused symmetry.
- [ ] No `from __future__ import annotations` (project-wide rule, guarded by
      `tests/test_core_contract.py`).
- [ ] New `tests/test_builtin_nodes.py`, unit level, no graph involved:
  - [ ] each op's happy path;
  - [ ] **purity**: the input collection is unchanged after every op (the property the DAG depends on);
  - [ ] fail loud: `list_get`/`list_remove_at` out of range → `IndexError`;
        `dict_get`/`dict_delete` on a missing key → `KeyError`; `set_remove` on an absent item →
        `KeyError`;
  - [ ] `set_to_list` is sorted and deterministic; raises `TypeError` on a mixed `{1, "a"}` set;
  - [ ] `set_add` with an unhashable item → `TypeError`;
  - [ ] `BUILTIN_FUNCTIONS` keys match the function names 1:1 and are all underscored (no dots).

### 3. Host wiring — `packages/coral-app/src/coral_app/__init__.py`

- [ ] `build_function_map` applies `BUILTIN_FUNCTIONS` **after** the plugin merge, so a builtin name
      always wins (decision 7):
      ```python
      function_map: Dict[str, Any] = {}
      for name in _selected(include, exclude):
          function_map.update(load(name).get_functions())
      function_map.update(BUILTIN_FUNCTIONS)   # host guarantee: not shadowable
      ```
  - [ ] Note the consequence in the docstring: the plugin-vs-plugin rule is still "later wins", but
        builtins sit outside that contest. A plugin declaring `list_append` is silently ignored — if we
        ever want that to fail loud instead, it is a separate change.
  - [ ] Key order: the builtins land **last** in the map, hence last in `node_types.json`. That keeps
        every existing entry in its original position, which step 4's golden diff checks.
  - [ ] A test pins the rule: a stub plugin-shaped mapping declaring `list_append` does not displace
        the builtin.
- [ ] Export `BUILTIN_FUNCTIONS` in `__all__` and mention it in the module docstring next to
      `PRIMITIVES_MAP`, as the second host-owned node surface.
- [ ] `build_class_map` unchanged.
- [ ] Tests in `tests/test_plugin_discovery.py`:
  - [ ] `build_function_map(include=[])` contains every builtin and nothing else — the "no plugin
        installed" contract.
  - [ ] `build_function_map()` (all plugins) contains every builtin as well.
  - [ ] the shadowing rule chosen above.

### 4. The registry — the goldens break, on purpose

`save_registry_to_file` always emits every primitive and every function in the map, so **all four
golden files change**, for every plugin set.

- [ ] Fix `tests/test_plugin_discovery.py:165` `test_register_with_no_plugins_emits_only_primitives`.
      Its assertion `set(registry) == set(PRIMITIVES_MAP)` is now false by design: with no plugins the
      registry holds the primitives **plus the builtins**. Rename it to say so
      (`..._emits_only_primitives_and_builtins`) and assert
      `set(registry) == set(PRIMITIVES_MAP) | set(BUILTIN_FUNCTIONS)`. Update the module docstring at
      line 13, which states the baseline is "primitives".
- [ ] Audit the rest of the suite for assertions that assume a plugin owns every function or that
      count map entries — `tests/test_registry.py`, `tests/test_plugins.py`,
      `tests/test_characterization.py`, `tests/test_acceptance.py`.
- [ ] Regenerate the four goldens, with **all three plugins installed** (`uv sync` first — the `all`
      case is `discover()`, so a missing plugin would bake a truncated golden):
  - [ ] `uv run coral -p "<name>" register --output=tests/golden/node_types.<name>.json` for
        `math`, `string`, `phiflow` — these three are compared **byte-for-byte**.
  - [ ] `uv run coral register --output=tests/golden/node_types.all.json` — **no `-p`**, since
        `GOLDEN_CASES["all"]` is `discover()` and the CLI's empty `-p` mirrors it. Compared by parsed
        content, not bytes.
  - [ ] **Read the diff**: it must contain only the new function entries (and the new primitive
        entries, if the open question above is resolved as (i) or (ii)), with every pre-existing entry
        byte-identical and in its original position.
- [ ] Assert the new entries' shape explicitly in `tests/test_registry.py`:
  - [ ] `list_append` has `arguments[0] == {"connection_type": "input", "type": "list", "name": "lst"}`
        — i.e. the collection socket is typed `list`, not `any`. This is the payoff of step 1.
  - [ ] `list_new` has `inputs: []` and `outputs: [0]`.
- [ ] **Platform risk to flag, not to fix here:** `list_new`/`set_new`/`dict_new` are the first
      *function* nodes with **zero inputs** the platform will see (primitives have no inputs but use
      `outputs: [-1]`, while a function uses `outputs: [0]`). Confirm the editor renders them before
      the feature is considered delivered.

### 5. Graph validation — `tests/test_graph.py`

No change to `graph.py`; bare `list`/`set`/`dict` annotations are plain classes, which check 6 already
handles via `issubclass`. Add cases to the existing type-compatibility class, using the file's local
`NodePorts` fixtures (no plugin needed):

- [ ] accept `list` → `list`, `set` → `set`, `dict` → `dict`.
- [ ] reject `list` → `set`, `list` → `float`, `str` → `list`, `dict` → `list`.
- [ ] skip (accept) `list` → `Any` and `Any` → `list` — e.g. `list_get`'s `Any` output feeding a
      typed port.
- [ ] a `list_new` node with an incoming edge fails check 4 (0 input ports, 1 edge).

### 6. End to end — workflow JSON fixtures (the desiderata's "Other Requirements")

- [ ] `tests/fixtures/valid_workflows/network-collections-list.json` — build, read back, measure:
      `list_new` → `list_append` ×3 (from `int` primitives) → `list_size` and `list_get`, plus a
      `list_remove_at`. Uses **no plugin at all**.
- [ ] `tests/fixtures/valid_workflows/network-collections-dict.json` — `dict_new` → `dict_set` ×2
      (`str` key, `float` value) → `dict_get` → `dict_delete` → `dict_size`.
- [ ] `tests/fixtures/valid_workflows/network-collections-set.json` — `set_new` → `set_add` ×3 with a
      duplicate → `set_size` (proving deduplication) → `set_to_list` → `list_get`.
- [ ] `tests/fixtures/valid_workflows/network-collections-math.json` — a collection feeding a plugin
      function, tagged `@pytest.mark.math`: `list_get` → `add`. This is the interop case decision 2
      turned on, so it deserves a fixture.
- [ ] Add a `TestCollectionWorkflows` class to `tests/test_integration.py` asserting each one's
      **result values**, not just that it runs: sizes, the extracted element, and that the collection
      a `*_append` fed into is unchanged in `executor.results` (purity, end to end).
  - [ ] The first three run with `plugins=[]` and are **untagged**; only the math one is tagged.
- [ ] Extend the `workflow_files` fixture (`tests/conftest.py:19-30`). It is a **hardcoded dict**, not
      a glob, so the new files are not discovered automatically — add the four keys
      (`collections_list`, `collections_dict`, `collections_set`, `collections_math`).
- [ ] `examples/collections/` — one runnable example mirroring the list fixture, so
      `coral run examples/collections/list.json` is a one-liner demo alongside `examples/phiflow/`.
      **Note:** the command loads every installed plugin, because `-p ""` resolves to `discover()`
      (`cli.py::_resolve_plugins`) — there is no CLI way to select *zero* plugins. The graph needs
      none of them; "runs without any plugin" is a property only the API (`plugins=[]`) can express,
      which is why the fixtures above assert it and the example cannot.

### 7. Documentation

- [ ] `CLAUDE.md`:
  - [ ] Project Overview — the four node kinds are unchanged, but the host now ships functions of its
        own; say so.
  - [ ] Package layout — add `builtin_nodes.py` to the `coral-app` tree with its one-line job.
  - [ ] Core components §3 — `build_function_map` is seeded with `BUILTIN_FUNCTIONS`; record the
        decision-7 precedence rule.
  - [ ] Data flow stage 1 — "load plugins" now also means "seed the host's builtins".
  - [ ] Type system bullet under Key Constraints — `PRIMITIVES_MAP` gains `list`/`set`/`dict`, and
        collection primitives are empty-only (decision 3).
  - [ ] Graph validation §"annotation quality" — the builtins are fully annotated, so add a row to the
        slots table.
  - [ ] A short "Built-in collection nodes" section: the 15 names, the purity and fail-loud contract,
        and that they need no plugin.
- [ ] `docs/ONBOARDING.md` — the narrative reason a shared operation is host-owned rather than a
      plugin (decision 1), and why the wire carries a bare `list` (decision 2).
- [ ] `tests/README.md` — the new test file, and the rule that builtin tests carry no plugin marker.
- [ ] Verify the subset claim still holds: `uv pip uninstall coral-plugin-math coral-plugin-string
      coral-plugin-phiflow` then `uv run --no-sync pytest` — the collection tests must **pass**, not
      skip. Restore with `uv sync`.
- [ ] `uv run pre-commit run --all-files`.
