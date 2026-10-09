# More ergonomic plugin registration — Plan

## Read first
- `decisions.md` (this folder): the why behind every step; "D<n>" below refers to it.
- `desiderata.md` (this folder): the working rules. Implement one step at a time and **pause after
  each step** for review; show every diff before applying it.
- Conventions that bite here: test docstrings are GIVEN/WHEN/THEN; no issue numbers in code
  comments/docstrings; no plugin name as a string literal under `coral-core/tests` or
  `coral-app/tests` (`tests/invariants/test_source_rules.py`).
- Strategy: a **temporary legacy adapter** (step 2, deleted in step 5) keeps every step green.
  Step 2 changes the host with every plugin untouched; each sub-step of 3 changes one plugin. A
  golden diff therefore always points at exactly one change.
- Golden commands:
  - plugins: `uv run coral -p "<name>" register --output=plugins/coral-<name>/tests/system/golden/node_types.<name>.json`
  - format golden: the command in `issues/46-support-multiple-inheritance/plan.md` step 6.1.
- After editing a plugin's entry point: `uv sync` (refreshes the editable install's metadata).
  Read the `uv.lock` diff: it must be empty.

## Steps

### 1. `coral-core`: the new `Plugin`
- [ ] 1.1 Declarations (D8), frozen dataclasses: `Declaration(target, inputs, outputs, annotations)`
      (a constructor's `target` is the class itself),
      `MethodDeclaration(attribute, declaration)`,
      `ClassDeclaration(target, constructor: Declaration, methods: {node method name: MethodDeclaration})`.
- [ ] 1.2 `Plugin` becomes concrete (no ABC). `function` / `cls` / `method`, each bare, with
      arguments, or as a call (D2), returning the target unchanged. Options and their
      decorator-time checks per D3, D4 and the errors table (rows "at the decorator").
- [ ] 1.3 `functions()` / `classes()`, lazy (D6): MRO walk; nearest mark; inheritance of
      `name=`/`inputs=`/`outputs=` but not `annotations=` (D7); non-function override
      `TypeError`; "marked but in no registered MRO" `ValueError`; method-name clash `ValueError`.
      Node order: registration order; methods in `dir()` order.
- [ ] 1.4 Transitional: `get_functions()` / `get_classes()` stay. Old subclasses override them; on
      a new-style instance they return `{name: decl.target}`. Removed in step 5.
- [ ] 1.5 Tests: new `coral-core/tests/test_plugin.py`: the three forms; every decorator-time
      check; lazy resolution independent of order; inheritance (registered and unregistered base,
      unmarked and re-marked override, annotations not inherited, non-function override, dead base
      mark not raising); cross-plugin non-inheritance and explicit re-mark; foreign method call
      form; order. `test_plugin_abc.py`: drop the abstractness tests (no longer true).
      `test_outputs.py` untouched until step 5.

### 2. Host on declarations, with the legacy adapter
- [ ] 2.1 `coral_app/__init__.py`: `load()` accepts a `Plugin` instance (new) or a `Plugin`
      subclass (legacy: instantiate). `build_function_map` / `build_class_map` return
      declarations instead of bare callables (`{name: Declaration}` / `{key: ClassDeclaration}`);
      every consumer reads `.target` where it needs the callable. A plugin is **legacy** when its
      class overrides `get_functions` (`type(p).get_functions is not Plugin.get_functions`), not
      when its entry point resolves to a class: the `specimen_plugins` fixture hands the host
      instances of legacy subclasses. A legacy plugin and `BUILTIN_FUNCTIONS` go through the **adapter**,
      which reproduces today exactly: function -> `Declaration(f, {}, output_names(f), {})`;
      class -> every public pure-Python method in `dir()` order, labels from `output_names`; an
      `__init__` carrying `@outputs` still refused.
- [ ] 2.2 `nodeports.build_port_table` consumes declarations: applies `annotations=` (fill),
      `inputs=` (relabel), `outputs=` (name) with the checks in the errors table; refuses
      non-positional parameters (D10); methods come from `ClassDeclaration.methods`
      (`_public_method_names` moves into the adapter); `NodePorts` gains `attribute`.
- [ ] 2.3 `executor`: `.target` for functions, constructors and the instance check
      (`class_map[class_name].target`); `getattr(instance, ports.attribute)`.
- [ ] 2.4 `registry`: `{cls: key}` built from `decl.target`.
- [ ] 2.5 Host tests: convert the `build_port_table` / `generate_registry` call sites
      (`test_nodeports.py`, `test_registry.py`, `test_graph.py`, …) to declarations built with
      `Plugin()` and its decorators. New tests: each `annotations=` / `inputs=` / `outputs=` check;
      D10 for keyword-only, `*args`, `**kwargs`; a renamed method executes; an unmarked override
      runs the override. The `datetime.date` test flips to expect the D10 refusal.
- [ ] 2.6 Verify: whole suite green; **all five goldens byte-identical** (format + four plugins).

### 3. Migrate, one sub-step each (D11)
Each: `plugin = Plugin()` with decorators; entry point -> `:plugin`; `uv sync`; its unit tests
(`test_plugin_conformance.py` rewritten for an instance; `test_plugin_present.py`: resolves to
`plugin`); **its golden byte-identical**.
- [ ] 3.1 `coral-string`.
- [ ] 3.2 `coral-math` (`@outputs` -> `outputs=`).
- [ ] 3.3 `coral-pypde` (`_holding` stays unmarked).
- [ ] 3.4 `coral-phiflow` (`@outputs` -> `outputs=`).
- [ ] 3.5 `coral-app/tests/specimen.py`: the six specimen plugins become instances; every
      currently public method marked (`_hidden` stays unmarked); `@outputs` -> `outputs=`;
      `PLUGINS` maps names to instances; the `specimen_plugins` fixture stops instantiating.
      The format golden is byte-identical.

### 4. Builtins (D9)
- [ ] 4.1 `builtin_nodes.py`: `BUILTINS = Plugin()`, the 15 functions decorated in today's order;
      `BUILTIN_FUNCTIONS` removed; re-export `BUILTINS`; `build_function_map` merges
      `BUILTINS.functions()` last.
- [ ] 4.2 Update `test_builtin_nodes.py`, `test_discovery.py`, `test_registry.py`,
      `tests/test_acceptance.py`, and the `errors.py` docstring. Format golden and plugin goldens
      byte-identical.

### 5. Remove the transition
- [ ] 5.1 Delete the adapter, `load()`'s legacy branch (a class is now a `TypeError`),
      `Plugin.get_functions` / `get_classes`, `outputs` / `output_names`, and
      `coral-core/tests/test_outputs.py` (its checks already live in `test_plugin.py`, step 1.5).
- [ ] 5.2 `tests/discovery/test_installed_plugins.py`: `get_*` -> `functions()` / `classes()`.
      `test_discovery.py`: a `Plugin` subclass entry point raises `TypeError`.
- [ ] 5.3 `grep` for `get_functions|get_classes|output_names|@outputs|BUILTIN_FUNCTIONS` outside
      `issues/` returns nothing. Suite green, goldens byte-identical.

### 6. New math nodes (D11)
- [ ] 6.1 `math.atan2`, `Fraction`, `Fraction.limit_denominator` via the call form.
- [ ] 6.2 Unit tests. The conformance test "every port annotated" reads the plugin's declarations
      (the signature plus `annotations=`), without the host, so `annotations=` counts.
- [ ] 6.3 An example graph in `plugins/coral-math/tests/graphs/` (every node with a
      `qualified_id`), validated and run in `tests/system/`, with value assertions, e.g.
      `math.atan2(1.0, 1.0) == pi/4` and
      `Fraction(3141592, 1000000).limit_denominator(1000) == Fraction(355, 113)`.
- [ ] 6.4 Regenerate the math golden: the diff is **additions only** (the three entries).

### 7. Documentation
- [ ] 7.1 `CLAUDE.md`: Core components, Adding a New Plugin (code, entry point, test-suite
      shape), Type Hint Requirements, the C-extension limitation, `BUILTIN_FUNCTIONS`.
- [ ] 7.2 `docs/ONBOARDING.md` (including lines ~171, 465, 614, 657) and `tests/README.md`
      (its wording on the ABC / `get_*` contract).

### 8. Final check
- [ ] 8.1 `uv run pre-commit run --all-files`; full `pytest` including `slow` and `network`.

## Exceptions to "each step has tests"
- Step 7 (docs) has none.
- Step 4 adds no new behaviour: its tests are the existing ones, kept green.
