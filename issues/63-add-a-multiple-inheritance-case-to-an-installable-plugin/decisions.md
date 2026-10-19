# #63 — Decisions

Context for implementing GitHub issue #63. #46 emits `bases` / `derived`, but its only multiple-
inheritance classes are in `coral-app/tests/specimen.py`, which `coral -p` cannot load. The
platform (dealiiX-platform PR #226, rule `{type} ∪ bases ∪ {base}`) needs the case in an
installable plugin. Plan: `plan.md`.

## Decisions
1. **In `coral-math`**, not a dedicated plugin: a fifth distribution costs a package, a suite and
   a new `-p` name for one fixture; math is already the demo plugin the platform loads.
2. **Names**: `Shape` (C), `Rectangle(Shape)` (B2), `Regular` (B1), `Square(Regular, Rectangle)`
   (A). `Regular` is the *first* parent and not a `Shape`, so `Rectangle` and `Shape` are reachable
   only through `bases`, never through the former `base`.
3. **Both methods and functions** consume the hierarchy: `Shape.area` / `Rectangle.diagonal`, and
   `area(s: Shape)` / `diagonal(r: Rectangle)`. Accepted cost: inherited method nodes
   (`Rectangle.area`, `Square.area`, `Square.diagonal`) enter the palette.
4. **`Shape` is abstract**, detected: an `ABC` whose `area` is an `@abstractmethod` declared with
   `@plugin.method`. It still meets #63: no graph needs a `Shape` node, only a `Square` accepted
   where a `Shape` is expected. The platform must handle `"node_type": "abstract"`.
5. **`Regular` is abstract with an empty body**: `plugin.cls(Regular, abstract=True)` — the explicit
   flag, since nothing makes it detectable. No zero-input constructor of a meaningless object.
6. **Signatures**:
   - `Rectangle(width: float, height: float)`; `area` an undeclared override (keeps the node);
     `@plugin.method diagonal(self) -> float` via `math.hypot`.
   - `Square(side: float)` → `Rectangle(side, side)`.
   - `@plugin.function(name="area") shape_area(s: Shape) -> float` and
     `@plugin.function(name="diagonal") rectangle_diagonal(r: Rectangle) -> float` delegate to the
     methods: one formula, one place. Python names differ so they do not read as the methods.
   - Each prints its result, as the other math nodes do.
   - No name clashes with another plugin or the builtins (checked).
7. **Graph** `tests/graphs/network-multiple-inheritance.json`: `float(3)` "side" → `Square` "square"
   → `diagonal` "diagonal_fn", `area` "area_fn", `Rectangle.diagonal` "diagonal_method",
   `Shape.area` "area_method". Every edge out of `square` lands on a `Rectangle` or `Shape` socket,
   none on `Regular`. Expected: area `9.0`, diagonal `math.hypot(3, 3)`, exact. No print nodes.
8. **Tests** (`plugins/coral-math/tests/`):
   - `unit/test_shapes.py`: arithmetic; `Square` is a `Regular`, `Rectangle`, `Shape`; `Shape()`
     raises `TypeError`; the functions equal the methods.
   - `system/test_graphs_run.py`: the graph's four values.
   - `system/test_registry.py`: golden regenerated; explicit `Square.bases == ["Regular",
     "Rectangle", "Shape"]`, `Shape.derived == ["Rectangle", "Square"]`,
     `Regular.derived == ["Square"]`; `test_every_declared_class_is_a_constructor_node` expects
     `"abstract"` for an abstract declaration.
   - `test_graphs_validate.py` unchanged (it globs `graphs/`).
9. **Docs**:
   - Math's description in `CLAUDE.md` / `README.md` plugin lists.
   - The `CLAUDE.md` slot table, recounted (not by hand).
   - The math module docstring: why the shapes exist.
   - The editor-regression passages in `CLAUDE.md` and `docs/ONBOARDING.md:681`: name the graph
     as the end-to-end case.
