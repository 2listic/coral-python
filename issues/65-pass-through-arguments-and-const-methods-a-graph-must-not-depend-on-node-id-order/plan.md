# #65 — Plan

## Read first
- `decisions.md` (this folder): the why behind every step. "Decision N" means its numbering.
- Pause at the end of every Step; tick boxes as part of the shown diffs.
- Conventions that bite here: test docstrings are GIVEN/WHEN/THEN; no issue numbers in code
  comments/docstrings (`tests/invariants/test_source_rules.py`); `ruff format` / `ruff check`.
- Order matters: plugins mark their read-only methods `const=True` (step 7) before any golden
  is regenerated, so the golden diffs show only genuine writers.
- The fast lane is red from step 3 (registry format) until step 10 (goldens): the
  pre-commit hook will refuse a commit in between.

## Steps

### 1. `coral-core/src/coral_core/__init__.py`: the declarations
- [ ] 1.1 `Declaration`: add `writes: tuple[str, ...] = ()`, last; docstring.
- [ ] 1.2 `MethodDeclaration`: add `const: bool = False`, last; docstring.
- [ ] 1.3 `_Mark`: add `const: bool` and `writes: tuple[str, ...]`.
- [ ] 1.4 `_writes(writes, where)` validator, beside `_inputs` / `_outputs`: `None` → `()`;
      a `str` → one name; a tuple/list of distinct non-empty `str`; else `TypeError` /
      `ValueError`. Names are checked against the signature by the host (step 2), as `inputs=`.
- [ ] 1.5 `Plugin.function`: keyword `writes=`; stored on the `Declaration`. Docstring.
- [ ] 1.6 `Plugin.method`: keywords `const: bool = False` (`TypeError` if not a `bool`) and
      `writes=`; stored on the `_Mark`. Docstring.
- [ ] 1.7 `Plugin.cls`: no `writes=` (decision 3) — nothing to add; docstring says so.
- [ ] 1.8 `_method` (decision 5): with `declared` and `func`, and the nearest declaration's
      mark:
      - `func is not declared` and `mark.const` → `ValueError` (undeclared override of a
        `const` method), message in the style of the `annotations=` one;
      - a *declared* override (`func` has its own mark) of a `const` declaration must be
        `const` → `ValueError`;
      - a declared override's `writes=` may not name a parameter, by position, that the base
        reads → `ValueError`, naming the parameter and both functions;
      - an undeclared override inherits `writes=` (and, of a non-`const` method, `const=False`).
      The positional comparison needs both functions' parameter lists: read with
      `inspect.signature` here, the one place core reads a signature — or deferred to the host.
      Settle it at review of this sub-step.
- [ ] 1.9 `_method` returns `MethodDeclaration(attribute, Declaration(func, …, writes),
      const)`.
- [ ] 1.10 Module docstring: `const=` and `writes=` in the options list.

### 2. `coral-app/src/coral_app/nodeports.py`: pass-through ports
- [ ] 2.1 `Port`: add `passthrough: Optional[int] = None` — on an **output**, the index of
      the input port it passes on; `None` for an ordinary output. And `written: bool = False`
      on an **input**. Docstrings.
- [ ] 2.2 `NodePorts`: add `returns: Optional[int] = None` — how many outputs are return
      values (what `outputs=` names and the arity check counts); `None` means all of them,
      for the kinds without pass-throughs. Docstring.
- [ ] 2.3 `_parameters`: validate `writes=` keys against the signature, like `inputs=` keys
      (a key naming no parameter raises; naming a method's instance raises — use `const`).
- [ ] 2.4 `_function_ports` / `_method_ports`: mark written inputs (a non-`const` method's
      port 0 included); build outputs in decision 4's order — the instance (non-`const`
      method), the return ports, then one pass-through port per written parameter in
      parameter order, each annotated and named as its input.
- [ ] 2.5 `_constructor_ports`: unchanged (`returns` stays `None`).

### 3. `coral-app/src/coral_app/registry.py`
- [ ] 3.1 `_create_input_argument`: `"connection_type": "pass_through"` for a written input.
- [ ] 3.2 `_number_outputs`: output arguments only for return ports; the `outputs` list in
      port order, a pass-through's entry being its input's argument index (so `outputs` may
      not be ascending — decision 4).
- [ ] 3.3 Docstrings of `_number_outputs`, `_add_function_node`, `_add_methods`,
      `generate_registry`.

### 4. `coral-app/src/coral_app/graph.py`
- [ ] 4.1 New check, after 8: **one writer per output** — per (source, normalised
      `source_output`), at most one edge into a written input. Message names the output and
      both writers.
- [ ] 4.2 `_build_order` (check 10, was 9): add implicit edges reader → writer for every output
      with a writer. A cycle through an implicit edge says so in the message: which reader,
      which writer, which value.
- [ ] 4.3 Renumber the checks after the new one in docstrings/comments (cycles become 10,
      literals 11).
- [ ] 4.4 `_output_annotation`: unchanged (a pass-through port carries its annotation).

### 5. `coral-app/src/coral_app/__init__.py`: `build_class_map`
- [ ] 5.1 Decision 8: after merging, a class whose `__mro__[1:]` contains a class registered
      by a *different* plugin raises (`ValueError` subclass? reuse `DuplicateNodeTypeError`
      or a new one — settle at review), naming both classes and both plugins.
- [ ] 5.2 Docstring.

### 6. `coral-app/src/coral_app/executor.py`
- [ ] 6.1 Dispatch (decision 7): build `{class: ClassDeclaration}` once from `class_map`;
      `_resolve` for a method takes the declaration of `type(instance)` and the
      `MethodDeclaration` with `ports.attribute`; calls `declaration.target(instance, *rest)`.
      No `getattr`. The `isinstance` check on port 0 stays, before the lookup. Comment and
      docstring updated.
- [ ] 6.2 Output bundle: when a node has pass-through outputs, assemble the stored result in
      port order from the instance / written arguments and the call's return value(s); a
      tuple only when there is more than one output (a non-`const` method returning `None`
      stores the instance itself).
- [ ] 6.3 `_check_output_arity`: compare against `ports.returns`, before 6.2's assembly.
- [ ] 6.4 Producer check (decision 7): after 6.3, every output value that is an instance of a
      registered class has `type(value)` in the class map; else `ValueError` naming node,
      output and class. Docstring placed beside the arity check's.
- [ ] 6.5 `_input_values`: unchanged in logic (it indexes by `len(outputs) > 1`, which now
      counts pass-throughs); re-read its docstring.

### 7. Plugins: declare `const` / `writes=`
- [ ] 7.1 Audit every declared method for writes to `self` (read only `__init__` assigns,
      seen during discussion; confirm per method).
- [ ] 7.2 math: `Calculator.get_value`, `Shape.area`, `Rectangle.diagonal`,
      `Fraction.limit_denominator` → `const=True` (`Square.area` / `.diagonal` resolve to
      `Rectangle`'s functions and follow them).
      `Rectangle.area` is an undeclared override of `Shape.area`: declare it
      `@plugin.method(const=True)` and fix its "Not declared again" docstring (decision 5).
      `Calculator.add_to_value`, `multiply_value` stay non-`const`.
- [ ] 7.3 string: `StringProcessor.concatenate`, `.repeat` → `const=True` if 7.1 confirms.
- [ ] 7.4 phiflow: `get_box`, `get_sphere`, `get_cuboid`, both `get_grid` → `const=True`.
- [ ] 7.5 pypde: `PyPDEScalarField.plot` / `.to_file`,
      `PyPDEObstacleDiffusionPDE.get_initial_condition` → `const=True` if 7.1 confirms;
      `PyPDEDiffusionPDE.solve` / `PyPDEObstacleDiffusionPDE.solve` — decide from 7.1 (they
      call into py-pde's `solve`).
- [ ] 7.6 Builtins: none has `writes=` (pure by contract); check nothing changes.

### 8. Graphs
- [ ] 8.1 `plugins/coral-math/tests/graphs/network-from-fe-classes.json`: rewire — chain
      `add_to_value` → (its pass-through) → `multiply_value`; renumber the `source_output`
      of every edge reading their results (now output 1). Its value assertions follow.
- [ ] 8.2 Every other shipped graph: re-run the scan from the discussion; migrate any edge
      reading a non-`const` method's output (expected: none after step 7).
- [ ] 8.3 `pytest plugins/*/tests/system/test_graphs_validate.py`: all construct.

### 9. Tests
- [ ] 9.1 `coral-core/tests/test_plugin.py`: `const=` (default, explicit, bad type);
      `writes=` (shapes, bad types, duplicate names); the three override rules of 1.8, each
      raising and each accepted case; inheritance by an undeclared override.
- [ ] 9.2 `coral-app/tests/specimen.py`: mark readers `const=True`, declaring their
      overrides `const=True` too (`Thermometer.read`, decision 5); add one writer with
      `writes=` (a function) and keep one non-`const` method; a new `hierarchy_clash_plugin`
      whose class derives from a specimen class, used only by 9.6. Module table, `__all__`.
- [ ] 9.3 `test_nodeports.py`: written inputs, pass-through outputs in decision 4's order,
      names, `returns`; `writes=` naming no parameter / the instance raises; `outputs=` counts
      only returns.
- [ ] 9.4 `test_registry.py`: a non-`const` method's exact entry (non-ascending `outputs`);
      a `writes=` function's entry; a `const` method unchanged.
- [ ] 9.5 `test_graph.py`: two writers on one output refused; readers ordered before the
      writer (check `order`); a reader depending on the writer's output → cycle message naming
      the implicit edge; normalised `source_output` (`0` / `-1` / omitted) count as one output.
- [ ] 9.6 `test_discovery` / `__init__` tests: cross-plugin hierarchy refused (decision 8).
- [ ] 9.7 `test_executor.py`: pass-through outputs carry the same object; dispatch runs a
      registered subclass's override (an unregistered one never gets there); the producer
      check refuses an unregistered subclass, through a typed and through an `Any` port;
      output arity counts only returns; existing `Meter` / `Child` tests still pass.
- [ ] 9.8 Plugin unit/system tests touched by step 7 and 8 (math's classes graph values).

### 10. Goldens
- [ ] 10.1 Regenerate `coral-app/tests/golden/node_types.format.json`; the diff shows only
      the specimen's writers.
- [ ] 10.2 Regenerate the four plugin goldens; the diff shows only `Calculator.add_to_value`
      / `multiply_value` (and pypde's `solve` if 7.5 keeps it non-`const`).

### 11. Docs
- [ ] 11.1 `CLAUDE.md`: Core components (`const=`, `writes=`, override rules, decision 3's
      unchecked contracts: no undeclared mutation, no aliasing of a read input, constructors
      modify no input), Registry Files
      (`pass_through`, non-ascending `outputs`), Node Execution Model (dispatch, bundle,
      producer check in the run-time checks table), Graph validation (new check, implicit
      edges, renumbering), Key Constraints (plugins do not share a hierarchy), Adding a New
      Plugin (example with `const=True`).
- [ ] 11.2 `docs/ONBOARDING.md`: the narrative of a graph not depending on node order.
- [ ] 11.3 `README.md`: only if it mentions method outputs.

### 12. Close
- [ ] 12.1 `uv run pre-commit run --all-files`; full `pytest` (slow lane included).
- [ ] 12.2 Short consistency audit of the result against `decisions.md`.
