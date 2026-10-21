# #65 — Decisions

Context for GitHub issue #65: a graph whose result depends on the order of two nodes that no edge
orders. Agreed in discussion, originally within #61, split out because it is a graph and protocol
change needed with or without concurrency. #61 depends on this issue.

## Findings (verified)
- The ambiguity exists with the sequential executor. One value fanned out to several nodes, one
  of which mutates it in place, gives a result decided by `graph.order`'s tie-break, i.e. by node
  ids: arbitrary but reproducible. A thread pool would make it non-reproducible.
  `plugins/coral-math/tests/graphs/network-from-fe-classes.json` is such a graph: one `Calculator`
  into `add_to_value` and `multiply_value`, both mutating `self.value`, so it computes
  `(v + a) * f` or `v * f + a` depending on node ids.
- Nothing in a Python signature says an output is a mutated input, and it cannot be detected:
  the AST misses mutation inside called code (`a.sort()`, `np.add(a, b, out=a)`, C extensions),
  a run-time comparison needs a copy. It must be declared.
- C++ declares it through its type system: a non-`const` reference parameter, or the instance of
  a non-`const` method, is a *pass-through* (`connection_type()`, `coral.h`). In
  `node_types.json` it is one argument with `"connection_type": "pass_through"` whose index is in
  both `inputs` and `outputs` (`coral-editor/test_files/vtk-single.json`,
  `Triangulation<2>::refine_global`). Outputs are listed in argument order
  (`coral.h:1485-1496`); argument order is `self`, return value, parameters for a method
  (`coral.h:854`), return value, parameters for a function (`coral.h:1046`). C++ does not refuse
  fanning one object into two non-`const` methods.
- The executor calls `getattr(instance, attribute)`, so the code that runs is decided by the
  instance's class, which may be one no plugin registers (a library subclass returned by a
  function annotated with its base). Such code was never declared, so no check before execution
  can cover it. No shipped plugin relies on an unregistered override, and the executor tests on
  override dispatch use registered subclasses (`test_executor.py`, abstract `Meter` /
  `Thermometer`, and `Child`).
- Shipped graphs fanning an instance into a method alongside other consumers:
  `network-from-fe-classes.json` (ambiguous), `network-multiple-inheritance.json`
  (`Rectangle.diagonal`, `Shape.area`: readers), `pypde/obstacles.json`
  (`get_initial_condition`, `solve`) and `pypde/poisson.json` (`to_file`, `plot`), the pypde
  methods presumably readers, to be checked.

## Decisions
1. **Methods are non-`const` by default.** `@plugin.method(const=True)` declares that a method
   does not modify its instance. A forgotten declaration never yields an order-dependent
   result: by 6, the method is ordered after the value's readers, or the graph is refused when
   another writer shares the value.
2. **A non-`const` method's instance is a pass-through**, in the C++ format: one argument, its
   index in both `inputs` and `outputs`.
3. **Any parameter can be declared written:** `writes=("arr",)` on `function` and `method`,
   its port a pass-through too. On a method, `const=` concerns the instance and `writes=` the
   other parameters, so adding a name to `writes=` can never turn a method `const` by omission.
   An undeclared parameter is read: that a node does not mutate what it does not declare is the
   author's contract, unchecked, like an annotation.
   Likewise unchecked: a node's outputs, and the state a constructed instance keeps, share no
   mutable object with a read input. A constructor or function that keeps or returns one
   copies it; otherwise a writer downstream modifies a value other nodes read, which the
   ordering of 6 cannot see.
   `cls` takes no `writes=`: a constructor modifies none of its inputs.
4. **Output order:** the instance (if written), then the return value(s), then the written
   parameters in parameter order. C++'s argument order, a tuple return's outputs taking the
   single return value's place. A pass-through is one argument, so it has one name, its
   input's (the parameter's or its `inputs=` label; the instance's is `self`); `outputs=`
   names, and counts, only the return values. Arguments keep their current order (parameters,
   then return values), so `outputs` may not be ascending: the editor reads it in list order
   (`UnifiedNode.svelte`, `canvasNodeUtils.ts`). Plugins first mark their read-only methods
   `const=True`, which leaves those entries unchanged; every non-`const` method gains output 0
   and its other outputs shift by one, so the shipped graphs reading them are migrated.
   This includes methods declared with the call form on classes the plugin does not write
   (`Fraction.limit_denominator`, phiflow's `get_*`).
   A return value named with `outputs=` may share its name with a pass-through: not refused,
   since a pass-through's name is its input's label and `inputs=` can always tell them apart.
   The port table stores no count of return values: `NodePorts.returns` derives them from the
   outputs that pass no input on, so the two cannot disagree.
5. **Overrides may promise more than their base, never less;** `classes()` raises otherwise:
   - an override of a `const` method must itself be declared `const=True` (an undeclared one
     raises, like `annotations=`);
   - a declared override may not write a parameter its base declares as read, compared by
     position;
   - an undeclared override inherits `writes=`.
   Every declared function under that attribute in the MRO is a base, not only the nearest: a
   method node of any of those classes, given an instance of this one, runs the override behind
   that class's ports. The nearest alone misses multiple inheritance (`D(B, C)`, `C.f` `const`,
   `B.f` not) and a declared function in an unregistered class in between.
   Positions are read in `coral-core` (`inspect.signature`), the one signature it reads: both
   functions are plain functions, and all of this stays in `classes()` rather than split with the
   host.
6. **Readers before the writer.** An output feeding a pass-through input feeds no other
   pass-through input: two writers of one value are refused, nothing would order them. It may
   also feed any number of read inputs; `Graph` then orders every such reader before the
   writer, as an implicit edge, so readers always see the value before it is modified. A
   reader that also depends on the writer's output closes a cycle and is refused by check 9.
   `source_output` is normalised first (`0`, `-1` and an omitted key are one output on a
   single-output node). Readers that should see the modified value read the writer's
   pass-through output instead. No copy, by the host or by a node.
7. **The executor runs only registered code.** A method node calls the function `classes()`
   resolved for the nearest registered class in `type(instance).__mro__`, never
   `getattr(instance, attribute)`. An override runs only if its class is registered (an
   undeclared override in a registered class runs, as 5 assumes); by 8, that class belongs to
   the node's own plugin.
   **Every class involved is registered.** Right after a node returns, each output value that
   is an instance of a registered class must be of a registered class itself
   (`type(value)` in the class map, whatever the port's annotation, `Any` included); otherwise
   the node fails, naming that class, before any consumer runs. Like the output-arity check,
   it confronts a declaration with a value, so it cannot run earlier. With it, every function
   that can run has been through the checks of 5.
8. **Plugins do not share a class hierarchy.** A class registered by one plugin may not derive
   from a class registered by another: `build_class_map` raises while merging, naming the two
   classes and the two plugins. In this repo plugins depend only on `coral-core`, so it can
   arise through a library both wrap; a third-party plugin may also depend on another plugin.
   Either way, one plugin registers the whole hierarchy. Values still cross plugins, code does
   not: with 7, a node runs only code its own plugin declared, and an abstract body is reached
   only through an unregistered class, which 7's check refuses.

## Rejected
- **Host-enforced copies** (deepcopy of a fanned-out written value): costly for large fields,
  impossible for some objects.
- **Ordering through the readers' pass-through outputs** (`val` into the readers, the writer
  fed from a reader's pass-through): orders only that reader before the writer unless the
  readers form a chain, which serialises them and gives every read input an extra socket.
- **A split node** fanning `val` out one socket per consumer: adds nodes, and orders nothing
  by itself.
- **A check at the consumer** (raise when a `const` method resolves to other code): fires only
  when that method is reached, possibly after other consumers of the same value have run. The
  producer check of 7 fires first, and for every method, not only `const` ones.
- **Trusting unregistered overrides:** leaves graphs that validate and still depend on order.
