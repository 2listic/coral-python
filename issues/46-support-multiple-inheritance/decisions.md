# #46 — Decisions

Context for implementing GitHub issue #46. Parallels coral-editor #63 (C++): the JSON must stay
coherent with it. Agreed in discussion; see `desiderata.md` for the goals. Plan: `plan.md`.

## Problem (verified)
- Validation and execution already respect Liskov for multiple parents, chains and any mix
  (desiderata 2–5): check 8 uses `issubclass` (`graph.py:83`), the executor `isinstance`
  (`executor.py:213`); both walk the full MRO, transitively.
- The registry records one ancestor only: `"base"` = first registered class in the MRO
  (`registry.py:105`). A second parent and the rest of the chain are lost, so the editor, which
  reads only `node_types.json`, cannot wire `A(B1, B2)` into a `B2` port.
- So #46 in Python is a registry-format change (desideratum 1).

## User experience
Unchanged for the plugin author: Python class syntax declares the parents, no `register_base`.
```python
class C: ...
class B2(C): ...
class A(B1, B2): ...
# get_classes() -> {"A": A, "B1": B1, "B2": B2, "C": C}
```
emits
```json
"A":  { ..., "bases": ["B1", "B2", "C"] },
"B2": { ..., "bases": ["C"], "derived": ["A"] },
"C":  { ..., "derived": ["A", "B2"] },
"B1": { ..., "derived": ["A"] }
```

## Decisions
1. **JSON as C++ #63**: constructor entries carry `"bases"` (all registered ancestors) and
   `"derived"` (all registered descendants); each key omitted when its list is empty. `"base"` is
   no longer written. Key order in the entry: `…, "type", "bases", "derived"` (where `base` sits
   today).
2. **Order** (C++ treats the lists as sets; our goldens are byte-compared): `bases` in MRO order,
   nearest first; `derived` in class-map order.
3. **Only class-map keys** are listed, as for `base` today:
   - an unregistered class in between is skipped; its ancestors are still found;
   - a type-name ancestor is not listed (`class MyFloat(float)` has no `bases`), though check 8
     accepts `MyFloat → float`: `bases` would otherwise mix class keys and type names;
   - the lists depend on the `-p` selection.
4. **Host tests pin desiderata 2–4** on check 8 and the executor (non-first parent, grandparent),
   though no host code changes there: today only single inheritance is tested.
5. **Editor regression accepted**, as in C++: the front end types a constructor's output as
   `base ?? type`; without `base` a subclass is refused where its base is expected, until it
   adopts the planned rule `{type} ∪ bases ∪ {base}`.

## Not carried over from C++
`register_base` API, casters, entry split, idempotence (Python class syntax declares the
parents); diamond handling (the MRO lists each ancestor once); sub-network SELF ports (nested
workflows are rejected by check 2).
