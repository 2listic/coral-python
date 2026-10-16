# #61 — Decisions

Context for GitHub issue #61: can the executor run independent nodes concurrently? Agreed in
discussion. The C++ reference backend already does (taskflow); this note fixes how Python follows.

## Findings (verified)
- C++ runs every network on a taskflow pool: `hardware_concurrency()` workers, overridden by the
  `THREADS` env var, forced to 1 when MPI is enabled (`backend_main.cc:648`). The platform's
  consumer therefore already sees overlapping `.running` markers.
- C++ const correctness orders mutations but does not forbid races: a non-`const` method's
  instance is a *pass-through* (input and output carrying the same object), so `A -> B` on one
  object is expressible; fanning one object into two non-`const` methods is not refused.
- Python's GIL: concurrency pays only for nodes that release it (numpy/BLAS kernels, numba
  `nogil`, jax, I/O) or on a free-threaded build.

## Decisions
1. **Thread pool only.** A process pool is dropped: every value crossing an edge would have to
   pickle, which the host cannot check, and a method mutating `self` would mutate a copy.
2. **Per-node `thread_safe`**, on `function`, `cls` and `method`; plugin-wide default via
   `Plugin(thread_safe=...)`, `False` when omitted. A plugin-wide `True` makes safe every node
   that does not state otherwise, including those added in later versions, without a per-node
   decision; that is the author's explicit choice.
   Host-owned nodes are safe: `BUILTINS = Plugin(thread_safe=True)`, since the collection
   functions are pure by contract; primitives are always safe and not declarable — they run no
   code, their value already read by `Graph`. Both still get their markers.
3. **`cls(thread_safe=...)` covers the constructor only**; it does not cascade to methods, which
   take the plugin default unless declared.
   On an abstract class it raises, as `inputs=` / `annotations=` do: there is no constructor for
   it to describe.
4. **Overrides:** when a base declaration states `thread_safe=` (either value), an undeclared
   override raises in `classes()` — like `annotations=`, it is a claim about a function body.
   `classes()` sees only registered subclasses, so the flag is also confronted at run time: if
   `type(instance)` resolves the method's attribute to a function other than the declared one
   (an unregistered subclass, e.g. a library's own subclass of a class declared with the call
   form), the node runs unsafe, whatever its flag. The cost of a wrong guess is a serialised
   node, never a race.
5. **Shared instances:** nodes whose inputs hold the same instance of a registered class (by
   `id`, on any port; `isinstance` against the class map, so unregistered subclasses count) are
   serialised at run time, whatever their kind or flag. Stricter than C++. It also serialises a
   read-only fan-out of one object (a field into several analyses): accepted, because at run
   time it cannot be told apart from a mutator fanned out with readers.
6. **Workers:** `THREADS` env var, as C++; default `os.cpu_count()`. No CLI flag. With
   `THREADS=1` the run is exactly today's: same order, markers and log (see 7).
   A set `THREADS` must be a positive decimal integer, else `ValueError` while the executor is
   constructed; unset or empty means the default; `os.cpu_count()` returning `None` means 1.
7. **Scheduling:** unsafe nodes share one host lock (never two at once); safe nodes run freely.
   The host lock and the instance locks of 5 are scheduler resources, not mutexes a worker
   waits on: a ready node is dispatched only when all of its resources are free, takes them at
   once and releases them when it ends. Among ready nodes, the first in `graph.order` whose
   resources are free goes. A running node therefore never waits on a host resource, so no
   deadlock can form, not even with a plugin's own mutex. Dispatch is the start: its
   `Start running` line and `.running` marker are written then, never while it waits.
   `thread_safe=True` means: touches no process-global mutable state (pyplot, global RNG, cwd,
   env, library-wide settings) that it does not guard itself, and is reentrant. Guarding: the
   plugin protects its own state with its own mutex and declares the node safe. The state of a
   library shared across plugins cannot be guarded that way, since each plugin would hold a
   different mutex: such nodes stay unsafe.
8. **Failure:** stop scheduling, let running nodes finish (they write their own markers),
   re-raise the first exception untouched; later failures are printed.
9. **Markers:** format unchanged; the warn-once flag is guarded by a lock.
10. **Logs:** host lines go through one lock (whole lines). A failing node prints
    `Node N [qid]: name (type = T) failed` before the exception propagates.
    The opening `Execution order: [...]` line becomes `Dispatch order: [...]`: under the pool it
    is the priority, not the order nodes ran in; that is read off the `Start running` lines.

## Future extensions (not in #61)
- **`coral_core.shared_lock(name)`**: one process-wide lock per name, so plugins sharing a
  library (e.g. `"matplotlib"`) exclude each other around the critical section only. Names by
  convention (the library's import name); nested locks risk deadlock.
- **Pass-through outputs for methods**, as C++: lets a graph order mutations on one object. A
  registry/protocol change; its own issue.
