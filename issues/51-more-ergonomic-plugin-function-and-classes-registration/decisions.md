# Decisions — more ergonomic plugin registration

## Context

Before: a plugin subclasses the `coral_core.Plugin` ABC and returns `{name: callable}` from
`get_functions()` / `get_classes()`; every public method of a registered class becomes a node;
output names come from a separate `@outputs` decorator that stores them on the function. The host
reads parameter names and types with `inspect.signature`, output names with `output_names(func)`.

After: a plugin is a `Plugin` **instance**; functions, classes and methods are registered with
decorators on it, which also carry every per-node option. Nothing is stored on the decorated
objects.

## The user experience

```python
# plugins/coral-math/src/coral_plugin_math/__init__.py
import math
from fractions import Fraction
from typing import Tuple

from coral_core import Plugin

plugin = Plugin()

@plugin.function                                              # node "add"
def add(a: float, b: float) -> float: ...

@plugin.function(name="test_tuple_return", outputs=("sum", "product", "difference"))
def tuple_return(x: float, y: float) -> Tuple[float, float, float]: ...

@plugin.function(name="math.pow", inputs={"x": "base", "y": "exponent"})
def math_pow(x: float, y: float) -> float: ...

@plugin.cls                                                   # node "Calculator" (constructor)
class Calculator:
    def __init__(self, initial_value: float): ...

    @plugin.method                                            # node "Calculator.add_to_value"
    def add_to_value(self, amount: float) -> float: ...

    @plugin.method(outputs="value")                           # node "Calculator.get_value"
    def get_value(self) -> float: ...

    def helper(self) -> None: ...                             # not a node

# Foreign callables, no wrapper (call form)
plugin.function(math.atan2, name="math.atan2",
                annotations={"y": float, "x": float, "return": float})
plugin.method(Fraction.limit_denominator,
              annotations={"max_denominator": int, "return": Fraction})
plugin.cls(Fraction, annotations={"numerator": int, "denominator": int})
```

```toml
[project.entry-points."coral.plugins"]
math = "coral_plugin_math:plugin"      # the instance; the entry-point name is unchanged
```

## Decisions

### D1 — Plugin shape
- `coral_core.Plugin` is a concrete class, no longer an ABC. A plugin is an instance of it.
- The entry point targets the instance. `load()` checks `isinstance(obj, Plugin)` (`TypeError`
  otherwise) and no longer instantiates.
- Each instance owns its own registry: no global state.

### D2 — Decorator names and forms
- `plugin.function`, `plugin.cls`, `plugin.method`.
- Each works bare (`@plugin.method`), with arguments (`@plugin.method(outputs="v")`), and as a
  plain call on an existing object (`plugin.function(math.atan2, ...)`).
- Each returns its target unchanged: the decorated function or class stays a normal Python object.

### D3 — What can be registered
- `function`: any callable that is not a class.
- `cls`: a class. Registering it always registers its **constructor** as the class's node; there
  is no constructor opt-out.
- `method`: a plain function (`inspect.isfunction`). A `staticmethod`, `classmethod`, property or
  builtin is refused with `TypeError`.
- **Methods are opt-in**: only marked methods become nodes. Any name may be marked, including `_x`
  and dunders, except `__init__` / `__new__` (`ValueError`: the constructor is the class's node).

### D4 — Options

| option | on | meaning |
| --- | --- | --- |
| `name=` | all three | the node name; default `__name__` (a method node is `<class key>.<name>`) |
| `inputs=` | all three | `{parameter: label}`; relabels only the listed input ports |
| `outputs=` | `function`, `method` | output names in port order; a plain `str` is one name |
| `annotations=` | all three | types for parameters (and `"return"`) the signature leaves unannotated |

- `name=`: a non-empty `str`. On `cls` and `method` it must not contain `.`: `A.b` + `c` and
  `A` + `b.c` would both give `A.b.c`. Function names may (`math.sqrt`).
- All options are **labels only**: wiring stays positional (`target_input` / `source_output`).
- `annotations=` **only fills gaps**. A key for a parameter that is already annotated (including
  an explicit `Any`) raises, so a declared type never contradicts the code.
- `@outputs` and `output_names` are **removed** from `coral_core`.

### D5 — Labels live in the plugin
- Options are stored in the plugin, never on the target: a builtin has no `__dict__`, and marking
  a foreign function would let two plugins overwrite each other.
- Method marks are kept in a table keyed by function object; functions and classes are keyed by
  node name.

### D6 — Resolution is lazy
- `plugin.functions()` / `plugin.classes()` resolve everything when the host asks, so decoration
  order does not matter (a foreign method may be marked before or after its class is registered).
- For each registered class, walk its attributes through the MRO. Attribute `m` is a method node
  if any class in the MRO marks `m`.

### D7 — Inheritance
- A registered subclass gets every method marked in its MRO (whether or not the base class is
  registered).
- An **unmarked override** keeps the node. It inherits `name=`, `inputs=` and `outputs=` from the
  nearest mark, but **not** `annotations=`, which describes one specific function's signature.
  Its ports come from the override itself.
- A **re-marked override** replaces the labels for that class and its descendants.
- At run time, `getattr(instance, attribute)` runs the override (polymorphism, as today).
- A mark counts as **collected** when its function is found in `vars(K)` for some `K` in the MRO
  of some registered class, even if an override shadows it. Only a mark found in no registered
  MRO raises.
- An override that is not a function (`m = None`, a property) raises `TypeError` in `classes()`,
  naming the class and the attribute.
- **Across plugins** marks are not inherited: a class registered by plugin B sees only B's marks.
  B can re-mark the inherited function itself: `plugin_b.method(Base.m)`.

### D8 — What the host receives
- `functions()` -> `{node name: Declaration}`.
- `classes()` -> `{class key: constructor Declaration + {method node name: (attribute, Declaration)}}`.
- `Declaration(target, inputs, outputs, annotations)`: the callable plus what the decorator said,
  as frozen dataclasses in `coral_core`. Exact shape to settle in the plan.
- `coral_core` never calls `inspect.signature` and builds no ports.
- `nodeports.build_port_table` stays the **only** place that builds ports. It reads the signature
  as today, then applies `annotations=` (fill), `inputs=` (relabel) and `outputs=` (name), in that
  order.
- `NodePorts` gains the method's attribute name. The executor calls
  `getattr(instance, attribute)` instead of splitting the node type.

### D9 — Builtins
- `coral_app/builtin_nodes.py` declares its 15 functions on `BUILTINS = Plugin()`, with the same
  decorators. It is not discovered by entry point, and is merged last as today.
- `BUILTINS` replaces the `BUILTIN_FUNCTIONS` dict and its re-export.

### D10 — Non-positional parameters are refused
- The executor calls positionally (`target(*values)`). `build_port_table` therefore raises
  `ValueError`, naming the node, for any keyword-only, `*args` or `**kwargs` parameter.
- Consequence: a class whose constructor has one cannot be registered at all, not even for its
  methods. This includes every C-extension class, which used to register a placeholder `args` /
  `kwargs` constructor. Such a class needs a wrapper.

### D11 — Migration
- The old subclass style is **removed**, not kept alongside. Migrate the four plugins, their
  entry points, `coral-app/tests/specimen.py` and the builtins.
- Existing wrappers are **kept** (phiflow and pypde adapt APIs; the math wrappers print and are
  tested for it).
- The migration must leave every golden `node_types.*.json` **byte-identical**. Node order is
  registration order, which matches today's dict order in all four plugins and the builtins;
  methods keep today's `dir()` (alphabetical) order.
- After the migration, the math plugin **adds** three nodes as living examples of the call form:
  `math.atan2`, `Fraction` and `Fraction.limit_denominator`, each with tests and an example graph.
  The math golden then changes by additions only.

## Errors: where and when

| check | where | when | error |
| --- | --- | --- | --- |
| target kind (D3) | `coral_core` | at the decorator | `TypeError` |
| `__init__` / `__new__` marked | `coral_core` | at the decorator | `ValueError` |
| `name=` not a non-empty `str`; `.` in a class or method name | `coral_core` | at the decorator | `TypeError` / `ValueError` |
| `outputs=`: not strings, none, empty, repeated | `coral_core` | at the decorator | `TypeError` / `ValueError` |
| `inputs=` not a dict of `str` -> non-empty `str`; `annotations=` not a dict with `str` keys | `coral_core` | at the decorator | `TypeError` / `ValueError` |
| duplicate node name in one plugin | `coral_core` | at the decorator | `ValueError` |
| one method marked twice in one plugin | `coral_core` | at the decorator | `ValueError` |
| one class registered twice in one plugin | `coral_core` | at the decorator | `ValueError` |
| one function under two names | — | — | allowed (an alias) |
| marked method in no registered class's MRO | `coral_core` | `classes()` | `ValueError` |
| two methods of one class resolving to one node name | `coral_core` | `classes()` | `ValueError` |
| inherited mark on a non-function attribute | `coral_core` | `classes()` | `TypeError` |
| no signature (`max`) | `nodeports` | `build_port_table` | `ValueError` |
| keyword-only / `*args` / `**kwargs` parameter | `nodeports` | `build_port_table` | `ValueError` |
| `inputs=` / `annotations=` key not a parameter; key `self`; `"return"` on `cls` | `nodeports` | `build_port_table` | `ValueError` |
| `annotations=` key already annotated | `nodeports` | `build_port_table` | `ValueError` |
| two input ports with one label | `nodeports` | `build_port_table` | `ValueError` |
| `outputs=` count differs from output ports | `nodeports` | `build_port_table` | `ValueError` (as today) |
| duplicates across plugins / with builtins / across kinds | host | as today | `DuplicateNodeTypeError` |

`coral_core` raises `ValueError` rather than `DuplicateNodeTypeError` because it must not import
the host.

## Out of scope
- Methods of C-extension classes (still not registrable; the class itself is now refused by D10).
- Hiding an inherited method node.
- Replacing the existing wrappers.

## Documentation to update
`CLAUDE.md` (Core components, Adding a New Plugin, Type Hint Requirements, the C-extension
limitation, `BUILTIN_FUNCTIONS`), `docs/ONBOARDING.md`, `tests/README.md`.
