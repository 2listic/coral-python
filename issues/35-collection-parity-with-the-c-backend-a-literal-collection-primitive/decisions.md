# #35 — Decisions

Context for implementing GitHub issue #35. Agreed in discussion. Plan: `plan.md`.
Background: `issues/25-add-lists-sets-and-dictionaries-to-the-base-type/review/pr-28-review-round-2.md` §2.5.

## Problem (verified)
- coral-python builds a collection only by chaining `list_new()` + n × `list_append` (the 15
  builtins in `coral_app/builtin_nodes.py`). `{"type": "list"}` is an unknown node type (check 4).
- The C++ backend (`dealII-X/repos/coral-editor`) has no collection operations; a collection is an
  *elementary type*, i.e. a node carrying a literal:
  `{"type": "std::set<unsigned int>", "value": "[1, 2, 3, 4, 5]"}` (`test_files/SetSum.json`).
- The two models are complementary: a literal cannot be built from computed values; the operations
  can. #35 adds the literal; the operations stay.

## How C++ and the editor handle `value` (verified, 2026-10-08)
- **C++** (`core/include/coral_implementation.h:851-863`): a non-network node's `value` **must be a
  JSON string**, else `"Non-network node 'value' must be a string."`. The string is parsed with
  `json::parse(value).get<T>()` (`core/include/coral.h:670`); `std::string` is stored raw. On
  output it writes the compact string (`"[1,2,3,4,5]"`).
- **C++ registry**: `std::set<unsigned int>` is the only collection registered;
  `node_type: "elementary_constructor"`, `outputs: [-1]`, default `"value": "[]"`
  (`json(T()).dump()`, `coral.h:642-656`). No list/vector, no map.
- **Editor** (`dealII-X/repos/dealiiX-platform`): every primitive except `bool` is a text box storing
  the typed string as-is (`src/lib/components/nodes/UnifiedNode.svelte:301-310`); export writes
  `value` unchanged (`src/lib/utils/graphParser.ts:348`). So the UI can only produce strings. A
  native array in an imported file survives an untouched round trip but displays as `1,2,3` and
  becomes free text on the first edit. Unknown type names (`list`/`set`/`dict`) get the text box, are
  always valid, and connect by exact type match or `any`.
- **Editor default value**: a dropped node copies the registry entry, so the registry's `value` is
  the initial text (`src/lib/utils/canvasNodeUtils.ts:46-64`).

## Decisions
1. **Bare `list` / `set` / `dict`**, elements untyped (`Any`). No element-typed names
   (`set[int]`): check 8 skips generic aliases, and the operations are untyped too. The type string
   therefore differs from C++ (`set` vs `std::set<unsigned int>`), as the scalars already do
   (`float` vs `double`): parity is of the *model*, not of the JSON.
2. **`value` is a JSON string, parsed with `json.loads`**: `"[1, 2]"` for `list` and `set`,
   `"{\"a\": 1}"` for `dict`. Same protocol as C++ (string → JSON parse → declared type) and the only
   thing the editor can produce. Not `ast.literal_eval`: Python syntax (`{1, 2}`, `{1: "x"}`) is not
   the protocol's.
   - A non-string `value` (a native array/object) is **rejected**, as in C++ — one spelling per
     value. Scalars are unchanged: `int` still accepts a native `42`.
     `any` is unchanged too: it passes `value` through as the JSON carried it, so a native
     `[1, "two"]` is accepted on an `any` node and rejected on a `list` node.
   - Shape is enforced: `list`/`set` need a JSON array, `dict` a JSON object; anything else raises.
     Never `list("[1, 2]")`, which silently yields characters.
   - JSON limits are accepted: dict keys are strings; a set is written as an array (duplicates
     collapse, as in `std::set`); an unhashable set element (a nested array) raises `TypeError`.
3. **`list_new` / `set_new` / `dict_new` stay.** An empty literal (`"[]"`) duplicates them; accepted
   to avoid breaking the shipped examples and fixtures.
4. **The literal is checked at execution**, in the executor's primitive conversion
   (`WorkflowExecutor._convert`), like `int("abc")` today. No new graph check. Primitives have no
   inputs, so they all run in the first batch of the order: a bad literal fails before any
   simulation. Moving all primitive casting into graph validation is a separate issue.
   The two errors the executor raises itself — a non-string `value` and a wrong shape — name the
   node (`graph.describe`), like the output-arity and method-instance checks. Errors raised by the
   parsing itself (`JSONDecodeError`, `TypeError` for an unhashable set element) propagate
   untouched, like `int("abc")`: the executor does not wrap a node's exception, and the per-node
   log line already names the node.
5. **One table**: `list`/`set`/`dict` join `PRIMITIVES_MAP`; `COLLECTION_TYPES` and `TYPE_NAMES`
   are deleted. The "reserved type name" refusal in `nodeports.py` is deleted too: a node type named
   `list` now collides with the primitive `list`, and the existing duplicate check refuses it
   ("declared as both a primitive and a …") — wherever primitives are passed to
   `build_port_table`, which the executor and registry always do.
6. **Registry default `value`**: `"[]"` for `list`/`set`, `"{}"` for `dict`; scalars keep `""`.
   Mirrors C++ (`"[]"` for its set); a node the user drops and leaves untouched is a valid empty
   collection. Aligning the scalar defaults with C++ (`"0"`, `"false"`) is out of scope.

## Consequences
- `"list"` / `"set"` / `"dict"` gain registry keys: every socket type name is now a
  `registry[...]` key, ending the novelty noted in `CLAUDE.md` (*Built-in collection nodes*).
- Every `node_types.*.json` golden (host + 4 plugins) gains three primitive entries.
- A graph using a collection literal still cannot run on C++ (type name differs), and vice versa.

## Out of scope (found while checking the editor)
- `UnifiedNode.svelte:289`: the `bool` checkbox binds `value`, not `checked`; an imported `"true"`
  is not shown ticked.
- `UnifiedNode.svelte:117`: `case (Type.DOUBLE, Type.FLOAT):` is the comma operator, so only
  `float` is validated; `double` never is.
