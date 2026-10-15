# #58 — Plan

## Read first
- `decisions.md` (this folder): the why behind every step.
- Phases: 3 = implement this plan; 4 = a short consistency audit of the result.
- Conventions that bite here: test docstrings are GIVEN/WHEN/THEN; no issue numbers in code
  comments/docstrings (`tests/invariants/test_source_rules.py`).

## Decisions
All agreed decisions, with their reasons, are in `decisions.md`; this plan does not restate them.
Step references to "decision N" mean `decisions.md`'s numbering.

## Steps

### 1. `coral-core/src/coral_core/__init__.py`
- [x] 1.1 `ClassDeclaration`: add `abstract: bool = False`, last; docstring (decision 3).
- [x] 1.2 `Plugin.cls`: keyword option `abstract: bool | None = None`. `TypeError` if not a
      `bool` or `None`. Resolve per decision 1's table; `False` on an `isabstract` class →
      `ValueError` naming `sorted(klass.__abstractmethods__)`. Resolved abstract with `inputs=` or
      `annotations=` → `ValueError` (decision 2). Docstring Args/Raises.
- [x] 1.3 `classes()`: carry `abstract` when rebuilding the declaration (`__init__.py:324`).
- [x] 1.4 Module docstring: one line on abstract classes.

### 2. `coral-app/src/coral_app/nodeports.py`
- [x] 2.1 `ABSTRACT = "abstract"`, in `__all__`; `NodePorts.kind` docstring lists five kinds.
- [x] 2.2 `build_port_table`: an abstract declaration gets `NodePorts(kind=ABSTRACT)`;
      `_constructor_ports` (and so `_signature`) is not called for it. Docstring.
- [x] 2.3 `put()`: the duplicate message's `a {kind}` reads "a abstract"; rephrase so the
      article fits every kind.

### 3. `coral-app/src/coral_app/registry.py`
- [ ] 3.1 `_add_constructor`: for `ports.kind == ABSTRACT` write `outputs: []` and
      `node_type: "abstract"`; `bases` / `derived` unchanged. Docstrings of `_add_constructor` and
      `generate_registry`.

### 4. `coral-app/src/coral_app/graph.py`
- [ ] 4.1 `_check_node_types_are_known` (check 4): refuse a node whose entry has
      `kind == ABSTRACT`, naming the node and the type, and saying it types sockets but is not a
      node. Docstring.

### 5. `plugins/coral-pypde/src/coral_plugin_pypde/__init__.py`
- [ ] 5.1 `plugin.cls(PyPDEGridBase, abstract=True)`, `plugin.cls(PyPDEShape, abstract=True)`
      (decision 4).

### 6. `coral-core/tests/test_plugin.py`: new `TestAbstractClasses`
- [ ] 6.1 The five rows of decision 1's table, one test each.
- [ ] 6.2 `inputs=` refused; `annotations=` refused; both for explicit and for detected abstract.
- [ ] 6.3 `name=` accepted: the key is the given name.
- [ ] 6.4 A method declared on an abstract class resolves on it and on a registered subclass.
- [ ] 6.5 `abstract="yes"` → `TypeError`.

### 7. Specimen and host tests
- [ ] 7.1 `coral-app/tests/specimen.py`: add `Meter(ABC)` — detected, not flagged — declaring
      `read(self) -> float` with `@specimen_plugin.method` over `@abstractmethod`, and
      `Thermometer(Meter)` with `__init__(self, celsius: float)` and an undeclared override of
      `read`. Module table and `__all__`. The explicit flag is covered by step 6 and by pypde.
- [ ] 7.2 `test_nodeports.py`: `Meter` has kind `ABSTRACT` and no ports; an ABC whose `__init__`
      is keyword-only is accepted; `Meter.read`'s port 0 is annotated `Meter`; the 2.3 message.
- [ ] 7.3 `test_registry.py`: the exact `Meter` entry; `Meter.derived == ["Thermometer"]`,
      `Thermometer.bases == ["Meter"]`; a socket typed `Meter` carries `"Meter"`.
      `test_the_golden_covers_all_four_kinds_and_the_builtins` (`:878`) → five kinds, renamed.
- [ ] 7.4 `test_graph.py`: `TestNodeTypes` — a `Meter` node is refused at construction with 4.1's
      message. `TestEdgeTypes` — `Thermometer` into `Meter.read` port 0 is accepted.
- [ ] 7.5 `test_executor.py`, `TestMethodNodes`: `Meter.read` on a `Thermometer` runs the
      override.
- [ ] 7.6 Regenerate `coral-app/tests/golden/node_types.format.json` (command in
      `TestFormatGolden`'s docstring). The diff must show only the new `Meter*` / `Thermometer*`
      entries.

### 8. Plugin and repo-level tests
- [ ] 8.1 `tests/discovery/test_installed_plugins.py:161`: expect `"abstract"` when the
      declaration is abstract, `"constructor"` otherwise.
- [ ] 8.2 `plugins/coral-pypde/tests/system/test_registry.py:55`: same rule; plus a test pinning
      that `PyPDEShape` and `PyPDEGridBase` are abstract (decision 4).
- [ ] 8.3 math / string / phiflow `test_registry.py`: unchanged — none declares an abstract class.
- [ ] 8.4 Regenerate `plugins/coral-pypde/tests/system/golden/node_types.pypde.json` (command in
      its module docstring). The diff must show only `PyPDEShape` and `PyPDEGridBase`:
      `outputs` `[-1]` → `[]`, `node_type` → `"abstract"`.

### 9. Docs
- [ ] 9.1 `CLAUDE.md`: the `plugin.cls` options (`abstract=`) and `ClassDeclaration` fields;
      Project Overview (abstract classes type sockets, are not nodes); the port-table kinds
      (`nodeports.py` bullet, *Node Execution Model*); *Registry Files* `node_type` list and the
      abstract entry; check 4 in *Graph validation*.
- [ ] 9.2 `CLAUDE.md` slot table: recount; expected pypde 55 → 53 slots, totals 183 → 181 and
      151 → 149 checkable.
- [ ] 9.3 `docs/ONBOARDING.md:141`, `:177`: the kind lists.

### 10. Verification
- [ ] 10.1 `uv run pytest` green; `uv run pre-commit run --all-files` clean.
- [ ] 10.2 Both golden diffs exactly as 7.6 and 8.4 say.
- [ ] 10.3 No issue numbers in code comments/docstrings (invariant suite).
