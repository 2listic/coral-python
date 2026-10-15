# Decisions: name a node's outputs with `@outputs`

Fixes [issue #18](https://github.com/2listic/coral-python/issues/18). The issue's diagnosis still
holds, but its references predate the refactor: there is no `_process_return_type` and no
`definitions/phiflow_defs.py` any more. The output name is now hardcoded in
`registry.py:_create_output_argument`, and the port table (`nodeports.py`) carries output
annotations only.

## The one-line diagnosis

An input is a parameter, so `inspect.signature` gives it a name. An output is a return value, and
Python has no syntax for naming one, so there is nothing to read. The editor renders
`arguments[i].name` as a socket's label (`UnifiedNode.svelte`), so every Python output shows a type
and a blank label. The C++ backend has names only because its author types them by hand in each
`register_function(...)` call, outputs included (there, outputs are by-reference parameters).
A name cannot be generated: it must be declared. This plan adds a way to declare it.

## Decisions

| # | question | decision | why |
| --- | --- | --- | --- |
| 1 | how are names declared? | a decorator that **only marks** the function: it sets one attribute and returns the same object | `inspect.signature`, annotations and `inspect.isfunction` keep seeing the original, so method discovery and the port table are unaffected; no call overhead; the executor never knows it exists. Keeps open a future decorator-based registration (decorators mark, the host scans) |
| 2 | where, and what names? | `coral_core.outputs` sets `_coral_outputs`; the host reads it only through `coral_core.output_names(func) -> tuple[str, ...] \| None` | `coral-core` is the only package both a plugin and the host may import. The reader keeps the attribute's name private to one module |
| 3 | call syntax | varargs: `@outputs("velocity", "smoke", "pressure")` | shorter. The list form's pitfall is silent (`@outputs("value")` would iterate a string); the varargs pitfall (`@outputs` with no parentheses) is caught by decision 4 |
| 4 | what is refused, and where | **in the decorator, at import:** a non-`str` name (`TypeError`), no names, an empty name, a duplicate name (`ValueError`). **In `build_port_table`:** a name count different from the output-port count (`ValueError` naming the node type) | each check runs where its facts are known: the names are local to the call, while the port count needs the annotation. The count check also covers a decorated function returning `None`. Duplicates are refused because two identical labels recreate the problem being fixed. No character rule: a name is a display label, never a key, a filename or an id |
| 5 | an undecorated function's outputs | `""`, as today | a placeholder would be a name nobody wrote. Only opted-in nodes change in the registry |
| 6 | port-table shape | a frozen dataclass `Port(name, annotation)`; `NodePorts.inputs` and `.outputs` are both `List[Port]` | one list per side, so names cannot drift from types; reads as `port.annotation`, not `[1]`; inputs and outputs share one representation |
| 7 | constructors | refused: the decorator refuses a non-function (`TypeError`), and `build_port_table` refuses a marked `__init__` (`ValueError` naming the class) | the registry writes a constructor's instance as `outputs: [-1]` with no output argument, so there is no `name` field to fill. Naming it would change the platform's format. Ignoring the mark would contradict fail-loud |
| 8 | which existing functions are decorated | only the two multi-output ones: `phiflow_iterate` → `velocity`, `smoke`, `pressure`; math's `test_tuple_return` → `sum`, `product`, `difference` | they are where outputs are indistinguishable. Single outputs are named, or not, by each plugin's owner |
| 9 | how do the host's own tests exercise `@outputs`? | decorate two **existing** specimen members: `split_triple` → `value`, `text`, `positive`; `Accumulator.add` → `total` | the framework suites may not use a real plugin, so the specimen must carry the decoration. These two already have the shapes needed (three outputs; a method), so two added lines cover a function, a method, and — through `PreciseAccumulator`, which inherits `add` — an inherited method. New members would only add test code. The host golden changes in exactly those three entries |

The steps that implement these are in [plan.md](plan.md).
