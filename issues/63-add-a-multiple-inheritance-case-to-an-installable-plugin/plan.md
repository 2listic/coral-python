# #63 — Plan

## Read first
- `decisions.md` (this folder): the why behind every step.
- Phases: 3 = implement this plan; 4 = a short consistency audit of the result.
- Conventions that bite here: test docstrings are GIVEN/WHEN/THEN; no issue numbers in code
  comments/docstrings (`tests/invariants/test_source_rules.py`).

## Decisions
All agreed decisions, with their reasons, are in `decisions.md`; this plan does not restate them.
Step references to "decision N" mean `decisions.md`'s numbering.

## Steps

### 1. `plugins/coral-math/src/coral_plugin_math/__init__.py`
- [x] 1.1 `Shape(ABC)` with `@plugin.cls`; `area(self) -> float` under `@plugin.method` over
      `@abstractmethod` (decision 4).
- [x] 1.2 `Rectangle(Shape)` with `@plugin.cls`: `__init__(self, width: float, height: float)`;
      undeclared `area`; `@plugin.method diagonal(self) -> float` via `math.hypot`; both print
      (decision 6).
- [x] 1.3 `Regular` with an empty body, declared `plugin.cls(Regular, abstract=True)`
      (decision 5).
- [x] 1.4 `Square(Regular, Rectangle)` with `@plugin.cls`: `__init__(self, side: float)` →
      `super().__init__(side, side)`.
- [x] 1.5 `@plugin.function(name="area") shape_area(s: Shape) -> float` and
      `@plugin.function(name="diagonal") rectangle_diagonal(r: Rectangle) -> float`, delegating
      to the methods, printing.
- [x] 1.6 `__all__` gains the four classes; module docstring: first line, and a paragraph on why
      the shapes exist (decision 9).

### 2. `plugins/coral-math/tests/graphs/network-multiple-inheritance.json`
- [x] 2.1 Six nodes as decision 7, with `name` and progressive `qualified_id`; five edges, all
      `source_output: 0`, `target_input: 0`. Same layout as `network-call-form.json`.

### 3. `plugins/coral-math/tests/unit/test_shapes.py` (new)
- [x] 3.1 `Rectangle(3, 4)`: `area() == 12.0`, `diagonal() == 5.0`.
- [x] 3.2 `Square(3)`: `area() == 9.0`, `diagonal() == math.hypot(3, 3)`.
- [x] 3.3 A `Square` is an instance of `Regular`, `Rectangle` and `Shape`.
- [x] 3.4 `Shape()` raises `TypeError`.
- [x] 3.5 `shape_area` / `rectangle_diagonal` return what the methods return, on a `Square`.

### 4. `plugins/coral-math/tests/system/test_graphs_run.py`
- [x] 4.1 New `TestTheMultipleInheritanceGraph`: the four values by `node_named` (decision 7).

### 5. `plugins/coral-math/tests/system/test_registry.py`
- [x] 5.1 `test_every_declared_class_is_a_constructor_node`: `"abstract"` when the declaration
      is abstract, `"constructor"` otherwise; rename to fit.
- [x] 5.2 New test: `Square.bases`, `Shape.derived`, `Regular.derived` as decision 8.
- [x] 5.3 Regenerate the golden (command in the module docstring). The diff must show only the
      new entries: `Shape`, `Rectangle`, `Regular`, `Square`, their five method nodes, `area`,
      `diagonal`.

### 6. Docs
- [x] 6.1 `CLAUDE.md:148`, `README.md:165`: math's description.
- [x] 6.2 `CLAUDE.md` slot table: recount with a script; expected math 36 → 50, totals
      181 → 195 and 149 → 163 checkable.
- [x] 6.3 `CLAUDE.md` "Subclasses depend on the front end" and `docs/ONBOARDING.md:681`: one
      sentence naming `network-multiple-inheritance.json` as the end-to-end case.

### 7. Verification
- [x] 7.1 `uv run pytest` green (slow and network included); `ruff format --check` and
      `ruff check` clean over `coral-core coral-app plugins tests`.
- [x] 7.2 The golden diff exactly as 5.3 says.
- [x] 7.3 `uv run coral -p "math" run plugins/coral-math/tests/graphs/network-multiple-inheritance.json`
      runs and prints the four values.
- [x] 7.4 No issue numbers in code comments/docstrings (invariant suite).
