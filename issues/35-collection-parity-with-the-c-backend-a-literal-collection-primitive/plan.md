# #35 — Plan

## Read first
- `decisions.md` (this folder): the why behind every step; "decision N" refers to its numbering.
- Conventions that bite here: test docstrings are GIVEN/WHEN/THEN; no issue numbers in code
  comments/docstrings (`tests/invariants/test_source_rules.py`); no
  `from __future__ import annotations`.

## Steps

### 1. `coral-app/src/coral_app/primitives.py` (decision 5)
- [ ] 1.1 Add `"list": list, "set": set, "dict": dict` to `PRIMITIVES_MAP`, after `"none"`
      (this order is the registry's key order).
- [ ] 1.2 Delete `COLLECTION_TYPES`, `TYPE_NAMES` and the comment above `COLLECTION_TYPES`.
- [ ] 1.3 Rewrite the module comment: a primitive carries a literal in `value`; scalars are cast by
      the type, collections parse a JSON string.

### 2. `coral-app/src/coral_app/__init__.py`
- [ ] 2.1 Drop `COLLECTION_TYPES`, `TYPE_NAMES` from the import and `__all__`; fix the module
      docstring if it mentions them.

### 3. `coral-app/src/coral_app/nodeports.py` (decision 5)
- [ ] 3.1 Delete the `COLLECTION_TYPES` import and the reserved-name check in `put`
      (`nodeports.py:279-282`).
- [ ] 3.2 Docstring of `build_port_table` (`nodeports.py:266`): drop the `Raises` clause about a node
      type named after a collection type; that case is now the primitive collision above it.

### 4. `coral-app/src/coral_app/registry.py` (decisions 5, 6)
- [ ] 4.1 `_TYPE_NAME_OF` built from `PRIMITIVES_MAP`; update its comment (`registry.py:9-11`), the
      `python_type_to_string` docstring (`registry.py:221`) and the comment at `registry.py:237`.
- [ ] 4.2 Primitive entries: `"value"` from a module-level
      `_DEFAULT_VALUE = {"list": "[]", "set": "[]", "dict": "{}"}`, via
      `_DEFAULT_VALUE.get(prim_type, "")`, with a comment: the editor copies it into a dropped node, so
      it must be a value the backend accepts.

### 5. `coral-app/src/coral_app/executor.py` — `_convert` (decisions 2, 4)
- [ ] 5.1 Signature `_convert(node)` → `_convert(node_id, node)`; its one call site is
      `executor.py:98`. For `list` / `set` / `dict`:
      1. `value` not a `str` → `ValueError` naming the node via `self.graph.describe(node_id)`,
         in the output-arity check's format:
         `Node '0' ('ids') of type 'set' needs a JSON string, got list`.
      2. `json.loads(value)`; a `JSONDecodeError` (a `ValueError`) propagates untouched.
      3. Shape: `list`/`set` require a JSON array, `dict` a JSON object; else `ValueError` naming
         the node the same way: `Node '0' ('ids') of type 'dict' needs a JSON object, got array`.
      4. Return `parsed` for `list`/`dict`, `set(parsed)` for `set` (`TypeError` on an unhashable
         element propagates untouched).
      Scalars, `any`, `none`: unchanged.
- [ ] 5.2 Docstring: the two rules (scalar cast vs JSON string).

### 6. Tests
Executor (`coral-app/tests/test_executor.py`, `TestPrimitiveNodes`):
- [ ] 6.1 `list` `"[1, \"a\", 2.5]"` → `[1, "a", 2.5]`; `set` `"[3, 1, 3]"` → `{1, 3}`;
      `dict` `"{\"a\": 1}"` → `{"a": 1}`; and `"[]"` / `"[]"` / `"{}"` → empty.
- [ ] 6.2 A native value (`[1, 2]` for `list`, `{"a": 1}` for `dict`) raises `ValueError`
      matching `Node '0' .* needs a JSON string`.
- [ ] 6.3 Wrong shape: `list` with `"{\"a\": 1}"`, `dict` with `"[1]"`, `set` with `"5"` raise
      `ValueError` matching `Node '0' .* needs a JSON (array|object)`.
- [ ] 6.4 Malformed JSON (`"[1, 2"`) raises `ValueError`.
- [ ] 6.5 Unhashable set element (`"[[1]]"`) raises `TypeError`.
- [ ] 6.6 A `set` literal wired into `set_size` executes (literal → builtin, check 8 accepts
      `set → set`).
- [ ] 6.7 `test_a_node_type_named_after_a_collection_is_refused` (`test_executor.py:79`): still
      raises `DuplicateNodeTypeError`; update the docstring (collision with a primitive, not a
      reserved name).

Graph (`coral-app/tests/test_graph.py`):
- [ ] 6.8 Replace `test_a_collection_is_not_a_node_type` (`:360`) with its opposite: with
      `build_port_table(primitives=PRIMITIVES_MAP)`, `list`/`set`/`dict` are primitive entries and a
      graph `{"0": {"type": "list", "value": "[]"}}` constructs.

Port table (`coral-app/tests/test_nodeports.py`):
- [ ] 6.9 `TestCollectionNamesAreReserved` (`:385`): rewrite as collisions with a primitive — pass
      `primitives=PRIMITIVES_MAP`; class `list` and function `dict` raise `DuplicateNodeTypeError`
      naming "primitive". Keep `test_a_method_named_after_a_collection_is_accepted`. Rename the class
      (e.g. `TestCollectionNamesCollideWithPrimitives`).

Registry (`coral-app/tests/test_registry.py`):
- [ ] 6.10 `test_collection_types` (`:59`): docstring — a collection is now a primitive node type.
- [ ] 6.11 `TestPrimitiveEntries`: add the `list` entry (`"value": "[]"`), `set` (`"[]"`),
      `dict` (`"{}"`); `test_a_class_named_after_a_collection_is_refused` (`:559`) unchanged in code,
      check the docstring.
      Expected `list` entry, mirroring `test_a_primitive_entry` (`:527`):
      `{"arguments": [], "value": "[]", "inputs": [], "outputs": [-1], "node_type": "primitive",
      "type": "list"}`.

Specimen (`coral-app/tests/specimen.py`):
- [ ] 6.12 `CollectionClashPlugin` docstring and module table (`:45`): the class keyed `list` now
      collides with the primitive `list`.

### 7. Goldens (decision 6)
Each gains exactly three entries (`list`, `set`, `dict`, after `none`); nothing else may change.
- [ ] 7.1 `coral-app/tests/golden/node_types.format.json` — the command in the `TestFormatGolden`
      docstring (`test_registry.py:764-771`).
- [ ] 7.2 `plugins/coral-{math,string,phiflow,pypde}/tests/system/golden/node_types.<n>.json` — the
      command in each plugin's `tests/system/test_registry.py` module docstring.

### 8. Example
- [ ] 8.1 `coral-app/examples/collections/literals.json`: a `list` literal `"[10, 20, 30]"` into
      `list_get` at `1`; a `set` literal `"[3, 1, 2, 3]"` into `set_size`; a `dict` literal
      `"{\"a\": 1}"` into `dict_get` at `"a"`. Every node with a `qualified_id` and a `name`.
      `test_examples.py` discovers it by glob and runs it with `plugins=[]`.
      Template: `coral-app/examples/collections/set.json` (envelope, node and edge shape). Wiring:
      `list_get(lst, index)` — port 0 the list, port 1 an `int` primitive `"1"` (→ `20`);
      `set_size(s)` — port 0 the set (→ `3`); `dict_get(d, key)` — port 0 the dict, port 1 a `str`
      primitive `"a"` (→ `1`).

### 9. Docs
- [ ] 9.1 `CLAUDE.md`:
      - *Package layout*: `primitives.py` comment (no more `COLLECTION_TYPES`).
      - *Core components* §3: re-exports (`PRIMITIVES_MAP` only).
      - *Data Flow* stage 3 / *Node Execution Model*: primitive nodes — collections parse a JSON
        string; the "named after a collection" refusal is now a primitive collision.
      - *Built-in collection nodes*: add the literal form; drop "`"list"` as a socket type that is
        not a registry key".
      - *Key Constraints → Type system*: rewrite (one table, nine primitive types).
      - *Registry Files*: primitive `value` defaults; `:413` "the nine names in `TYPE_NAMES`" →
        the nine names in `PRIMITIVES_MAP`.
- [ ] 9.2 `docs/ONBOARDING.md`: `:177-178` (`TYPE_NAMES`, "six primitive node types"), `:228`
      ("six-primitive map"), `:506-507` ("six `PRIMITIVES_MAP` node types", `COLLECTION_TYPES`),
      and the collections section `:590-610` — add the literal form and its relation to C++.

### 10. Verification
- [ ] 10.1 `uv run pytest` green; `uv run pre-commit run --all-files` clean.
- [ ] 10.2 `grep -rn "COLLECTION_TYPES\|TYPE_NAMES"` over `coral-core coral-app plugins tests docs
      CLAUDE.md README.md` — empty (except `issues/`).
- [ ] 10.3 Golden diffs: only the three new entries each.
- [ ] 10.4 `coral run coral-app/examples/collections/literals.json` from the CLI.
