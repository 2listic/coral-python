# #58 — Decisions

Context for implementing GitHub issue #58. The issue calls them "type-only" classes; the code calls
them **abstract**, the name the C++ backend and the front end already use for the same thing. The JSON
must stay coherent with both. Agreed in discussion. Plan: `plan.md`.

## Problem (verified)
- Registering a class has two effects that cannot be separated: its key becomes a socket type (and
  enters `bases` / `derived`), and it becomes a constructor node the editor offers.
- `coral-plugin-pypde` wants only the first for `PyPDEGridBase` (types `PyPDEScalarField`'s `grid`)
  and `PyPDEShape` (types `PyPDEObstacleDiffusionPDE`'s `source` / `absorber` / `obstacle`). Both are
  also zero-input constructor nodes building objects with no `.grid` / `_build_mask`: a graph using
  one passes validation and fails at run time.

## Prior art (verified)
- **C++** (`coral/core/include/coral.h:733`): `register_abstract_type<T>()` writes
  `"node_type": "abstract"`, `arguments` / `inputs` / `outputs` all `[]`, plus `bases` / `derived`.
  `register_base<T, B>()` registers an unregistered base as abstract. A graph node of an abstract
  type is not refused: it yields a null pointer at run time.
- **Front end** (dealiiX-platform): `NodeType.ABSTRACT` exists; it is hidden from the sidebar
  (`HIDDEN_SIDEBAR_NODE_TYPES`) and skipped by both compatible-node searches
  (`canvasNodeUtils.ts:181`, `:273`). `filterValidNodes` accepts the entry (it requires only
  `node_type`, `arguments`, `inputs`, `outputs`). `derived` is read nowhere.

## Decisions
1. **Declaration**: `plugin.cls(X, abstract=...)`. Omitted, `inspect.isabstract(X)` decides;
   `abstract=True` always wins; `abstract=False` on an `isabstract` class raises at the decorator,
   naming the class and its unimplemented abstract methods. Python refuses `X()` for such a class,
   so a constructor node would be exactly the defect this issue removes.

   | `abstract=` | `isabstract(X)` | result |
   | --- | --- | --- |
   | omitted | False | constructor |
   | omitted | True | abstract |
   | `True` | either | abstract |
   | `False` | False | constructor |
   | `False` | True | **error** |

2. **Options**: on an abstract class `inputs=` and `annotations=` are refused at the decorator —
   both describe constructor parameters, and there is no constructor. `name=` stays: it is the
   socket type key. Declared methods stay allowed: they run on a concrete instance (check 8 accepts
   a subclass at port 0, the executor's `isinstance` passes), and every registered subclass
   inherits the node.
3. **Host representation**:
   - `ClassDeclaration` gains `abstract: bool = False`, as its last field, so existing positional
     constructions and equality stay valid.
   - The port table gains a fifth kind, `abstract`: no inputs, no outputs, no attribute. Its
     signature is never read, so an ABC whose `__init__` cannot be passed by position is no longer
     refused.
   - Registry: written at the constructor's position (key order unchanged), in the C++ shape:
     `arguments: []`, `inputs: []`, `outputs: []`, `node_type: "abstract"`, `type`, then `bases` /
     `derived` as for a constructor. It stays in the class map, so a socket it types carries its key.
   - Check 4 refuses a node whose type is abstract, with a message of its own. Stricter than C++,
     and coherent with "every defect raises before the first node runs".
   - The duplicate checks (one name as two kinds, one class under two keys) apply unchanged.
   - The executor is unchanged: validation keeps an abstract node from reaching it.
4. **pypde**: `abstract=True` on `PyPDEShape` and `PyPDEGridBase`, not ABCs. `PyPDEGridBase`'s
   contract is an instance attribute (`self.grid`), which an abstract property would never satisfy:
   both grids would become uninstantiable. Converting `PyPDEShape` alone would mix two mechanisms
   in one plugin. Turning them into ABCs is left to the plugin's owner.

## Known, not addressed here
- The front end matches socket types by exact string and does not read `bases`: a `PyPDECircle`
  is still refused where a `PyPDEShape` is expected (CLAUDE.md, *Subclasses depend on the front
  end*). #58 removes the bogus constructor nodes, not this.
