# Plan: `pypde` as a coral plugin

## Situation

Branch `pypde-plugin` adds three files over its base: `definitions/pypde_defs.py` (old-style module,
6 wrapper classes, `get_functions() -> {}`), `pypde/examples/myexample.py` (a plain Python script,
not a coral graph), and a `data` line in `.gitignore`. **Nothing in it has ever run through coral** —
there is no graph — so this is a port *and* a first execution.

## Decisions

| # | question | decision | why |
| --- | --- | --- | --- |
| 1 | node surface shape | wrapper classes whose annotations **name the wrapper types** | graph check 8 verifies every edge at t=0; `Any` everywhere (phiflow's bargain) would skip all of them |
| 2 | how much of the example survives | **all 6 concepts**, movie included | the mp4 is what the author was demonstrating; ffmpeg is already required by phiflow's `slow` test, so it is not a new dependency |
| 3 | how `solve` receives its trackers | **one typed port per tracker** | coral cannot type a list's *elements*, so routing trackers through `list` hands back exactly the checking decision 1 paid for |
| 4 | the orphan `phiflow_write` commit | **out of scope** | no code dependency — `pypde_defs.py` imports only `pde`. It needs its own redesign: its three optional ports are dead under check 6 |
| 5 | where output goes | a **filename port**, no `data/` default | `phiflow_plot_and_save` already takes its filename as a port; `data/` was the author's local habit, not a design |
| 6 | `PyPDEMovie` + `PyPDEPlotTracker` | **kept separate**, 1:1 with py-pde | faithful to the library's own layering |
| 7 | what `solve` returns | **`PyPDEScalarField`**, the final state | the only return that composes; a second solve or a plot can chain off it |
| 8 | tests | the documented plugin shape, execution marked `slow` | the run test is the only thing that catches the old code's class of bug (`ScalarField` stored instead of instantiated) |

## The surface

```python
class PyPDEUnitGrid:
    def __init__(self, x: int, y: int)

class PyPDEScalarField:
    def __init__(self, grid: PyPDEUnitGrid, vmin: float, vmax: float)   # random_uniform

class PyPDEFileStorage:
    def __init__(self, filename: str, write_mode: str, interrupts: float)

class PyPDEMovie:
    def __init__(self, filename: str, framerate: int, dpi: int, bitrate: int)

class PyPDEPlotTracker:
    def __init__(self, movie: PyPDEMovie, interrupts: float)

class PyPDEDiffusionPDE:
    def __init__(self, diffusivity: float)
    def solve(self, state: PyPDEScalarField, t_range: int,
              storage: PyPDEFileStorage, plot: PyPDEPlotTracker) -> PyPDEScalarField
```

Three notes:

- `get_functions()` returns `{}`. pypde is the first plugin with **no function nodes** — legal, the
  ABC only requires the method.
- `PyPDEPlotTracker` unwraps its movie at construction (`self.movie = movie.movie`), so `solve` ends
  with `plot.movie.save()` rather than a double hop.
- `solve` wraps py-pde's returned field back into `PyPDEScalarField` through an **internal**
  classmethod, not a node: the public constructor makes a *random* field and must stay that way.
- Both trackers take their own `interrupts` — the schedule, in simulation time, on which each is
  invoked. Separate ports because they are genuinely independent: storage at `0.1` and plot at `1`
  gives an HDF5 with ten times the frames of the movie. Typed `float`, so only py-pde's
  `ConstantInterrupts` form is reachable from a graph; its string and list forms are not.

## Steps

1. **Create the distribution** — `plugins/coral-pypde/{pyproject.toml, src/coral_plugin_pypde/__init__.py}`.
   Name `coral-plugin-pypde`, entry point `pypde = "coral_plugin_pypde:PyPDEPlugin"`,
   `dependencies = ["coral-core", "py-pde", "h5py"]`, `[dependency-groups] test = ["coral-app"]`. The
   `import pde` is unconditional — no `try/except AVAILABLE`.
2. **Wire the workspace** — one line in the root `pyproject.toml`:
   `coral-plugin-pypde = { workspace = true }`. Nothing else: `members`, coverage `source` and
   `testpaths` are all globs that already match. Then `uv lock && uv sync`, and **read the `uv.lock`
   diff** — it must contain the new package and its closure, nothing more.
3. **Write the wrappers** per the surface above.
4. **Write the example graph** — `plugins/coral-pypde/examples/pypde/diffusion.json`: 21 nodes
   (6 constructors + 1 method + 14 primitives), 20 edges, every node carrying a progressive
   `qualified_id`. Both filenames are primitive ports, so a run writes into the cwd.
5. **Write the test suite**:
   ```
   plugins/coral-pypde/tests/
   ├── pypde_suite.py                  PLUGIN_NAME="pypde", MODULE_NAME, INSTALLED, EXAMPLES, GOLDEN
   ├── conftest.py                     the collect-time guard + isolate_cwd
   ├── unit/test_plugin_present.py     entry-point name, and that it is this package's
   ├── unit/test_plugin_conformance.py the ABC
   ├── unit/test_wrappers.py           each class against py-pde directly
   └── system/
       ├── test_graphs_validate.py     parametrised over examples/ (no graphs/ — decision 8)
       ├── test_graphs_run.py          @pytest.mark.slow, one run, asserts the .hdf5 and .mp4 exist
       ├── test_registry.py            byte-compared
       └── golden/node_types.pypde.json
   ```
6. **Record the golden** — `coral -p "pypde" register --output=…`, inspected before it is committed.
7. **Update the docs that enumerate plugins** — `CLAUDE.md` (package-layout tree + "Available
   plugins"), `README.md:102`, `docs/ONBOARDING.md:69`.
8. **Verify** — `pytest plugins/coral-pypde/tests`, `pytest -m "not slow"`,
   `uv run pre-commit run --all-files`, and the subset-install check
   (`uv pip uninstall coral-plugin-pypde && pytest` → named skips, no errors).

## Out of scope

`phiflow_write` (decision 4) · the `data` `.gitignore` line (decision 5) · `definitions/` and
`pypde/` from the old branch — never copied, so there is nothing to delete on this branch · a
builtin-list tracker example (decision 3).

## Verified against py-pde 0.58.0

A full run of the example's shape under `-W error` wrote both files and emitted nothing, so:

- `PDEBase.solve` returns the final state — a `pde.fields.scalar.ScalarField`. Decision 7 holds.
- **`h5py` is not a py-pde dependency**: it sits behind the `io` extra. Step 1 declares it directly
  rather than taking `py-pde[io]`, which would also pull `pandas`, `ffmpeg-python` and
  `py-modelrunner` for nothing.
- No `filterwarnings` entry is needed in `pytest.ini`.

Three signatures differ from what the old code assumed:

- `Movie(filename, framerate=30, dpi=None, **kwargs)` — **`bitrate` is not a parameter**, it is a
  documented passthrough to matplotlib's `FFMpegWriter`. The port forwards into `**kwargs`. `Movie`
  raises `RuntimeError` at construction when ffmpeg is missing, which is the fail-loud we want.
- `FileStorage`'s `write_mode` default is `"truncate_once"`, and everything after `filename` is
  keyword-only.
- `UnitGrid(shape)` takes a sequence, so the `(x, y)` wrapper is a real simplification.
