# #46 — Plan

Parallels coral-editor #63 (C++). Goals: `desiderata.md`.

## Read first
- `decisions.md` (this folder): the why behind every step.
- C++ counterpart: `/home/matteo/Projects/dealII-X/repos/coral-editor/issues/63-derived-types-multi-level-inheritance/decisions.md`
  (the JSON format comes from its decision 4).
- Phases: 3 = implement this plan; 4 = a short consistency audit of the result.
- Conventions that bite here: test docstrings are GIVEN/WHEN/THEN; no issue numbers in code
  comments/docstrings (`tests/invariants/test_source_rules.py`).

## Decisions
All agreed decisions, with their reasons, are in `decisions.md`; this plan does not restate them.
Step references to "decision N" mean `decisions.md`'s numbering.

## Steps

### 1. `coral-app/src/coral_app/registry.py`
- [ ] 1.1 `_add_constructor`: replace `base` with
      `bases = [class_names[c] for c in cls.__mro__[1:] if c in class_names]` and
      `derived = [name for other, name in class_names.items() if other is not cls and issubclass(other, cls)]`;
      write each only if non-empty. No signature change (`class_names` keeps class-map order).
- [ ] 1.2 Docstrings: `_add_constructor` and `generate_registry` (now `registry.py:153`).

### 2. Specimen (`coral-app/tests/specimen.py`)
- [ ] 2.1 Add `Resettable` (a second parent: own `__init__(self, level: float)`, method
      `reset(self) -> float` returning `0.0`) and `Ledger(PreciseAccumulator, Resettable)` (no
      body of its own). MRO: `Ledger, PreciseAccumulator, Accumulator, Resettable`: chain and
      multiple parents at once.
      `Ledger` inherits `PreciseAccumulator.__init__(start: float, digits: int)`; `Resettable.__init__`
      never runs on a `Ledger`, hence `reset` returns a constant, not state.
- [ ] 2.2 Register both in `SpecimenPlugin.get_classes()` after `PreciseAccumulator`
      (`Resettable`, then `Ledger`); update the module table and `__all__`.

### 3. Registry tests (`coral-app/tests/test_registry.py`): `TestBase` → `TestBases`
- [ ] 3.0 Delete today's `TestBase` (`test_registry.py:342–432`, 7 tests); 3.1–3.10 replace it.
- [ ] 3.1 Specimen: `Ledger.bases == ["PreciseAccumulator", "Accumulator", "Resettable"]`
      (MRO: the chain precedes the second parent).
- [ ] 3.2 Specimen: `Accumulator.derived == ["PreciseAccumulator", "Ledger"]`,
      `PreciseAccumulator.derived == ["Ledger"]`, `Resettable.derived == ["Ledger"]`.
- [ ] 3.3 Absent when empty: `Accumulator`/`Gauge` have no `bases`; `Ledger`/`Gauge` no `derived`.
- [ ] 3.4 `D(A, B)` → `D.bases == ["A", "B"]`.
- [ ] 3.5 Diamond `D(B, C)`, `B(A)`, `C(A)` → `D.bases == ["B", "C", "A"]`, `A` once.
- [ ] 3.6 Unregistered intermediate: `C(B(A))`, only `A`, `C` → `C.bases == ["A"]`,
      `A.derived == ["C"]`.
- [ ] 3.7 Key, not `__name__`: `{"Root": A, "B": B}` → `B.bases == ["Root"]`,
      `Root.derived == ["B"]`.
- [ ] 3.8 `derived` follows class-map order: `B(A)`, `C(A)` registered `{"A", "C", "B"}` →
      `A.derived == ["C", "B"]`.
- [ ] 3.9 Type-name ancestor: `class MyFloat(float)` → no `bases` key.
- [ ] 3.10 No entry of any kind carries `"base"`; no method entry carries `bases`/`derived`.

### 4. Check-8 tests (`coral-app/tests/test_graph.py`, `TestEdgeTypes`)
- [ ] 4.1 Add local `Cog` and `Gear(Sprocket, Cog)`; port-table entries `Cog`, `Cog.spin`, `Gear`.
- [ ] 4.2 `Gear` into `Widget.resize` → accepted (grandparent through a chain).
- [ ] 4.3 `Gear` into `Cog.spin` → accepted (non-first parent).
- [ ] 4.4 `Sprocket` into `Cog.spin` → rejected, `match=r"feeds Sprocket .* expects Cog"`
      (a sibling's parent is not an ancestor). Model: `test_unrelated_class_is_rejected`.

### 5. Executor tests (`coral-app/tests/test_executor.py`, `TestMethodNodes`)
- [ ] 5.1 A `Ledger(start=1.0, digits=2)` into `Accumulator.add` with `amount=2.0` → `3.0`
      (grandparent). Model: `test_a_subclass_instance_is_accepted` (`test_executor.py:404`).
- [ ] 5.2 A `Ledger` into `Resettable.reset` runs → `0.0` (non-first parent).

### 6. Golden
- [ ] 6.1 Regenerate `coral-app/tests/golden/node_types.format.json`. The diff must show only:
      `PreciseAccumulator` `base` → `bases`, the new `derived` keys, and the new
      `Resettable*`/`Ledger*` entries.
      Command (verified to reproduce today's golden byte for byte):
      ```bash
      uv run python -c "
      import sys; sys.path.insert(0, 'coral-app/tests')
      import coral_app, specimen
      coral_app.load = lambda n: specimen.PLUGINS[n]()
      from coral_app.registry import save_registry_to_file
      save_registry_to_file('coral-app/tests/golden/node_types.format.json', plugins=[specimen.SPECIMEN, specimen.RIVAL])"
      ```
- [ ] 6.2 `TestFormatGolden` docstring (`test_registry.py:680`): replace the stale line
      `uv run python -c "..."   # see the command in the test below` with the 6.1 command,
      indented as a `::` literal block. Test code unchanged.

### 7. Docs
- [ ] 7.1 `CLAUDE.md` *Registry Files*: the `base` bullet → `bases`/`derived`.
- [ ] 7.2 `CLAUDE.md` *Subclasses depend on the front end*: rewrite for the regression and the
      planned front-end rule.
- [ ] 7.3 `docs/ONBOARDING.md` (extension points): `base` → `bases`/`derived`; drop
      "recorded as its first registered parent only".

### 8. Verification
- [ ] 8.1 `uv run pytest` green; `uv run pre-commit run --all-files` clean.
- [ ] 8.2 No `"base"` key left in `src`, tests or goldens; every plugin golden unchanged.
- [ ] 8.3 No issue numbers in code comments/docstrings (invariant suite).
