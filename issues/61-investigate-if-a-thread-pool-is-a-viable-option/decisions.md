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
   `Plugin(thread_safe=...)`, `False` when omitted. A plugin-wide `True` makes every later node
   safe without a decision; that is the author's explicit choice.
3. **`cls(thread_safe=...)` covers the constructor only**; it does not cascade to methods, which
   take the plugin default unless declared.
4. **Overrides:** when a base declaration states `thread_safe=` (either value), an undeclared
   override raises in `classes()` — like `annotations=`, it is a claim about a function body.
5. **Shared instances:** method nodes whose port 0 holds the same object (`id`) are serialised at
   run time, whatever their flag. Stricter than C++.
6. **Workers:** `THREADS` env var, as C++; default `os.cpu_count()`. No CLI flag. With no safe
   node the run is serial, as today.
7. **Scheduling:** unsafe nodes share one host lock (never two at once); safe nodes run freely.
   `thread_safe=True` means: touches no process-global mutable state (pyplot, global RNG, cwd,
   env, library-wide settings) and is reentrant. Finer cases: the plugin guards its own state
   with its own mutex and declares the node safe. A library shared across plugins stays unsafe.
8. **Failure:** stop scheduling, let running nodes finish (they write their own markers),
   re-raise the first exception untouched; later failures are printed.
9. **Markers:** format unchanged; the warn-once flag is guarded by a lock.
10. **Logs:** host lines go through one lock (whole lines). A failing node prints
    `Node N [qid]: name (type = T) failed` before the exception propagates.

## Future extensions (not in #61)
- **`coral_core.shared_lock(name)`**: one process-wide lock per name, so plugins sharing a
  library (e.g. `"matplotlib"`) exclude each other around the critical section only. Names by
  convention (the library's import name); nested locks risk deadlock.
- **Pass-through outputs for methods**, as C++: lets a graph order mutations on one object. A
  registry/protocol change; its own issue.
