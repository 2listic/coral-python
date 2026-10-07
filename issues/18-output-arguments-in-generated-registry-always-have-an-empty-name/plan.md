# Plan: name a node's outputs with `@outputs`

Fixes [issue #18](https://github.com/2listic/coral-python/issues/18). The diagnosis and the
decisions, with their reasons, are in [decisions.md](decisions.md); decision numbers below refer to
it.

## Before you start

- Read `CLAUDE.md` (the mechanics reference), then `decisions.md`. Everything below assumes both.
- Rules that bind every step:
  - Every file change is shown as an exact diff and approved before it is applied. Never commit.
  - Test docstrings use GIVEN / WHEN / THEN.
  - No issue, PR, step or decision numbers in code, docstrings or tests: "decision 4" belongs in
    these two files only. Keep the reasoning, drop the citation.
  - No `from __future__ import annotations` (enforced by `tests/invariants/test_source_rules.py`).
  - `graph.py` must not import `inspect` and `executor.py` must not introspect (same invariants
    file): `Port` lives in `nodeports.py`, and `graph.py` only reads its fields.
- Done means: `uv run pytest` passes, `uv run pre-commit run --all-files` is clean, and the three
  golden diffs (Steps 4 and 5) touch only the entries named there.

## Steps

### Step 1 — `coral-core`: the decorator and its reader

- [ ] `outputs(*names)` in `coral-core/src/coral_core/__init__.py` (the package's only module; today
      it holds just `Plugin`). Two layers, so each check fires at the right moment:
      - the outer call validates `names`, in this order: every name is a `str` (`TypeError`), which
        is what catches a bare `@outputs`, since that calls `outputs(func)`; at least one name; no
        empty name; no duplicates (`ValueError`);
      - the inner `mark(func)` refuses anything for which `inspect.isfunction` is false (a class, a
        `staticmethod`/`classmethod` object, a builtin) with `TypeError`, then sets
        `func._coral_outputs = names` and returns `func` itself, with no wrapper.
- [ ] `output_names(func)`: `getattr(func, "_coral_outputs", None)`.
- [ ] Add both to `__all__`; extend the module docstring.

### Step 2 — `nodeports.py`: `Port`, and names into the table

- [ ] `Port(name: str, annotation: Any)`, frozen; export it.
- [ ] `NodePorts.inputs` / `.outputs` become `List[Port]`; `_input_ports` and the method's
      `self` port build `Port`s. Primitives and constructors get `Port("", type)`.
- [ ] Functions and methods: zip `output_names(callable)` with the annotations from
      `_outputs_from_return`; a count mismatch raises `ValueError` naming the node type and both
      counts. Unmarked → every name `""`.
- [ ] Constructors: a marked `__init__` raises `ValueError` naming the class.
- [ ] Where: `Port` sits next to `NodePorts`. The names are attached by one new helper called from
      `_function_ports` and `_method_ports`, after `_outputs_from_return`, which keeps returning
      annotations and keeps its tuple rejections. For a method, `getattr(cls, method_name)` is the
      plain function, so its mark is visible. An inherited method carries its base's mark: with
      `Accumulator.add` decorated, `PreciseAccumulator.add` gets the same names. That is intended,
      since it is the same function. The marked-`__init__` check reads `output_names(cls.__init__)`
      in `_constructor_ports`, so a subclass inheriting a marked `__init__` is refused too.
- [ ] Wording of the two new errors: model it on the tuple rejection in `_outputs_from_return`
      (name the node type or class, say what to write instead). Show it before applying.

### Step 3 — consumers read `Port`

- [ ] `registry.py`: `_create_input_argument` / `_create_output_argument` take a `Port`; the output
      argument writes `port.name`.
- [ ] `graph.py`: `_check_edge_types` unpacks `ports.inputs[...]` → read `.name` / `.annotation`;
      `_output_annotation` returns an output → return its `.annotation`.
      `_check_every_input_is_connected` and `_check_output_ports_exist` only take `len(...)`, so
      they are unchanged. `registry.py:_number_inputs` unpacks `for name, annotation in ...` too.
- [ ] `executor.py`: no change (it only takes `len(...)`); confirm.

### Step 4 — plugins

- [ ] `coral-phiflow`: `@outputs("velocity", "smoke", "pressure")` on `phiflow_iterate`.
- [ ] `coral-math`: `@outputs("sum", "product", "difference")` on `tuple_return`.
- [ ] Regenerate both goldens, from the workspace root:
      `uv run coral -p "math" register --output=plugins/coral-math/tests/system/golden/node_types.math.json`
      `uv run coral -p "phiflow" register --output=plugins/coral-phiflow/tests/system/golden/node_types.phiflow.json`
      Each diff must touch exactly that one entry's three output `name`s.

### Step 5 — tests (GIVEN/WHEN/THEN docstrings)

- [ ] `coral-core/tests`: the decorator returns the same object; `output_names` reads it back, or
      `None`; each import-time refusal.
- [ ] `coral-app/tests/test_nodeports.py`: names reach the table for a function and a method;
      unmarked → `""`; count mismatch refused; marked `__init__` refused; asserts move to `Port`.
- [ ] `coral-app/tests/specimen.py`: decorate `split_triple` with
      `@outputs("value", "text", "positive")` and `Accumulator.add` with `@outputs("total")`, and
      note both in the module docstring's table. `PreciseAccumulator` inherits `add`, so it covers
      the inherited mark.
- [ ] `coral-app/tests/test_registry.py`: the names reach `node_types.json` for a function, a
      method and an inherited method; undecorated outputs stay `""`.
- [ ] Regenerate the host golden (it has no CLI, because the specimen is not installed):
      ```bash
      uv run python -c "
      import sys; sys.path.insert(0, 'coral-app/tests')
      import coral_app, specimen
      coral_app.load = lambda n: specimen.PLUGINS[n]()
      from coral_app.registry import save_registry_to_file
      save_registry_to_file('coral-app/tests/golden/node_types.format.json',
                            plugins=[specimen.SPECIMEN, specimen.RIVAL])"
      ```
      The diff must touch only the output `name`s of `split_triple`, `Accumulator.add` and
      `PreciseAccumulator.add`.
- [ ] `coral-app/tests/test_graph.py`: fixtures move to `Port`, with no logic change.

### Step 6 — documentation

- [ ] `CLAUDE.md`: the `nodeports.py` bullet (`inputs`/`outputs` are `Port`s), *Registry Files*
      (an output's `name`), *Type Hint Requirements* and *Adding a New Plugin* (`@outputs`).
- [ ] `docs/ONBOARDING.md`: lines 174 and 272 describe the port table's old shape.

## What does not change

- The executor, and wiring: `source_output` stays positional; names are for display only.
- The registry's shape: keys, `inputs`/`outputs` indices, the `[-1]` constructor convention.
- Every undecorated node's registry entry.

## Out of scope

- Naming a constructor's output (needs a registry format change on the platform side).
- Naming single outputs in the plugins.
- Replacing `get_functions` / `get_classes` with decorator registration.
