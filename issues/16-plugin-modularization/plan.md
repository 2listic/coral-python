# Issue #16 — Plugin Modularization: Implementation Plan

Implement the `pyplug` skeleton **structure** (from `RECONSTRUCTION.md`) inside coral-python,
replacing the placeholder `name`/`describe` contract with coral's real surface
(`get_functions()` / `get_classes()`). coral-python **is** the "full-fledged app"; `pyplug` is only
the skeleton's stand-in name — no package is literally named `pyplug`.

## Start here (clean context)

If you're picking this up fresh, before doing anything:

1. Read this file top to bottom.
2. Read `issues/16-plugin-modularization/RECONSTRUCTION.md` — the skeleton spec whose **structure**
   is the invariant (its `name`/`describe` contract is the placeholder we replace with coral's
   `get_functions()`/`get_classes()`).
3. Skim the current code you'll be moving: `executor.py`, `registry.py`, `main.py`, `coral-py`,
   `definitions/` (`__init__.py`, `primitives.py`, `math_ops.py`, `string_ops.py`, `phiflow_defs.py`),
   `pyproject.toml`, and `tests/`.
4. All eight decisions (D1–D8) are **already made** (recorded below). Do not re-open them unless you
   hit a genuine blocker; if you do, raise it rather than deciding unilaterally.
5. Begin at **Step 0**.

## How to use this plan

- Work **top-level step by top-level step, in order**.
- **Every top-level step ends green**: its final substep is `uv sync && uv run pytest` with the full
  suite passing. Substeps inside a step may transiently break imports; the step as a whole must not.
- **All decisions D1–D8 are resolved** (see below). Each records the choice and its rationale; follow
  it. Nothing is left as `[DECIDE TOGETHER]`.
- Check a box (`- [x]`) only when done and verified.

---

## Recap — the agreed architecture (design is locked)

**Structure (the invariant, from the skeleton):**
- Monorepo, `src/` layout, uv workspace, one hatchling wheel per package.
- Discovery via stdlib `importlib.metadata` entry points, group **`coral.plugins`**, **lazy**:
  `discover()` lists names with **no import**; `load(name)` calls `ep.load()`, importing **only** that
  one plugin, validates it is a `Plugin` subclass (`TypeError` otherwise), and instantiates it
  (`PluginClass()`, no host context). Unknown name → `LookupError`.
- Strict dependency direction: **core → nothing internal; app → core; each plugin → core; the host
  never imports a plugin.**

**Contract — `coral-core` (minimal, ABC only):**
```python
class Plugin(ABC):
    @abstractmethod
    def get_functions(self) -> dict[str, Callable]: ...
    @abstractmethod
    def get_classes(self) -> dict[str, type]: ...
```
No `name`, no `describe` — the entry-point name is the plugin's identity.

**Host — `coral-app` (the main program):**
- `cli.py` (register / run), `registry.py`, `executor.py` — **bodies unchanged**.
- `discover` / `load` / `load_all` + `build_function_map` / `build_class_map` (same signatures as
  today, bodies re-backed by entry points).
- **`PRIMITIVES_MAP` lives here**, in the host — not in core (no plugin references it).

**Plugins — `coral-plugin-math` / `-string` / `-phiflow`:**
- Each subclasses `Plugin`; today's dict-returning bodies move into the class.
- Entry-point **names are exactly `math` / `string` / `phiflow`** (preserves the platform `-p`
  contract — non-negotiable).
- `coral-plugin-phiflow` owns the `phiflow` / `jax` / `h5py` dependencies.

**Preserved external contracts (must stay byte-identical):**
- The `register` output (`node_types.json`) for any given module set.
- Graph execution results and stdout behavior of `run`.
- The CLI surface (`-p <modules> register|run`) and the `coral-py` launcher's cwd-preserving role.

**Data flow:**
```
discover() (no import) ─→ load(requested names) ─→ plugin.get_functions()/get_classes()
   ─→ host merges → function_map / class_map ─→ registry.py (register) | executor.py (run)
```

---

## Decisions (all resolved — D1–D8)

- [x] **D1 — Migration strategy. DECIDED: A (lean atomic).**
      No throwaway shims. Step 1 adds the workspace root + `coral-core` purely additively (green,
      nothing imports it yet). Step 2 is the single big move: create `coral-app` + all plugins, move
      all code, rewrite all test imports, update `coral-py`, delete the flat files — green at the
      step's end. The D2 golden files give byte-level safety across the move. (Rejected: strangler
      with shims — its only extra benefit, isolating the move from the entry-point rewrite, is
      largely covered by the golden net and not worth the churn at this codebase size.)
- [x] **D2 — Golden-file contract tests. DECIDED: yes, folder `tests/golden/`.**
      In Step 0, snapshot `node_types.json` for `math`, `string`, `phiflow`, and all-modules from
      **today's** code into `tests/golden/`, and assert byte-identical output after the move. This is
      how we *prove* the registry contract is preserved across the atomic Step 2.
- [x] **D3 — No `from __future__ import annotations`. DECIDED: forbid it, project-wide.**
      It stringizes annotations, which would make `registry.py:python_type_to_string` see `"float"`
      instead of `float` and collapse every socket to `"any"` — silently breaking the registry.
      Add a guard test that no plugin or host module imports it. (Current code doesn't use it; this
      locks in the status quo.)
- [x] **D4 — Unknown-module behavior in `build_*_map`. DECIDED: B (fail-loud).**
      An unknown / not-discoverable `-p` name raises `LookupError` and aborts the invocation (no
      silent partial registry). This is a deliberate, small change from today's warn-and-skip:
      `register` no longer tolerates a stray name in the operator's free-text `-p` field — it fails
      loud at Save & Sync with a clear message. Pin with a test.
- [x] **D5 — Drop the phiflow `AVAILABLE` try/except guard. DECIDED: drop.**
      `coral-plugin-phiflow` **declares** `phiflow`/`jax`/`h5py` as hard deps, so installing the
      plugin guarantees availability; a broken/partial install now raises `ImportError` (loud)
      instead of silently registering nothing. (Lazy discovery already means an unselected phiflow is
      never imported.)
      *Coherence (D4+D5): one rule — "asked for but not fully available ⇒ stop." Not-installed →
      `LookupError` (D4); installed-but-broken → `ImportError` (D5). No silent partial state.*
- [x] **D6 — Launcher form. DECIDED: console script.**
      `coral-app` declares `[project.scripts] coral = "coral_app.cli:main"`; `coral-py` changes from
      `... python main.py "$@"` to `exec uv run --quiet --project "$HERE" coral "$@"` (keeps the
      no-`cd`, cwd-preserving trick). The platform keeps pointing `coralBinaryPath` at `coral-py` —
      nothing changes on its side.
- [x] **D7 — Test layout. DECIDED: Option 1 — single root `tests/` (for now).**
      One `tests/` tree (unit + integration + golden), run by one `pytest` from the root against the
      workspace-installed editable packages. A finer per-package / hybrid layout is deferred as a
      future concern. The heavy **wheel/pip acceptance** stays a standalone `scripts/acceptance.sh`,
      **not** collected by pytest (needs its own clean venv + `uv build`).
- [x] **D8 — Stragglers (out-of-scope files). DECIDED.**
      Leave `phi_flow/` demos and root `network-from-fe.json` (the `run` default) untouched; keep
      `requirements.in` / `requirements.txt` as legacy reference. **Delete `registry-py.json`** —
      but only after confirming no test references it; if one does, adjust rather than break the
      suite (the delete must not turn the suite red).

---

## Step 0 — Baseline & safety net

- [x] 0.1 Record the current green baseline: run `uv run pytest -q`, note the **exact test count** and
      that all pass. Capture it at the top of a scratch note. → **88 passed** (Py 3.14.6).
- [x] 0.2 *(needs D2)* If golden tests are approved: generate today's registry for each module set and
      save under `tests/golden/` —
      `node_types.math.json`, `node_types.string.json`, `node_types.phiflow.json`, `node_types.all.json`
      (via `python main.py -p "<set>" register --output=...`). Add a test asserting current
      `save_registry_to_file(..., modules=<set>)` output equals each golden file **byte-for-byte**.
      → `tests/test_golden_registry.py`.
- [x] 0.3 Add characterization tests (if not already covered) pinning `run` results for one small
      math graph and one string graph — the executor's returned `results` dict and key stdout lines.
      → `tests/test_characterization.py`.
- [x] 0.4 Confirm the baseline suite (existing + new golden/characterization) is green.
      `uv sync && uv run pytest` → all pass. → **94 passed**.

## Step 1 — Workspace root + `coral-core` (additive; no shims)

- [ ] 1.1 Create the virtual workspace root `pyproject.toml`: `[tool.uv.workspace] members =
      ["packages/*"]` and `[tool.uv.sources]` cross-linking every internal package
      (`{ workspace = true }`). **No `[project]` table** at the root. The old
      `[tool.uv] package = false` / flat-project metadata stays at the root **for now** so the flat
      code keeps importing until Step 2 (it migrates into `coral-app` there).
- [ ] 1.2 Create `packages/coral-core/` — `pyproject.toml` (hatchling; `name = "coral-core"`;
      `requires-python = ">=3.12"`; `dependencies = []`; wheel target `src/coral_core`) and
      `src/coral_core/__init__.py` with the `Plugin` ABC (two `@abstractmethod`s, `__all__ = ["Plugin"]`).
- [ ] 1.3 `uv sync` — verify `coral-core` installs editable and the old flat code is untouched
      (nothing imports `coral_core` yet).
- [ ] 1.4 Add `tests/test_core_contract.py`: `Plugin` cannot be instantiated; a subclass missing
      either method cannot be instantiated; a complete subclass can. *(D3)* Add the
      "no `from __future__ import annotations`" guard test.
- [ ] 1.5 `uv sync && uv run pytest` → all green (baseline count + new core tests).

## Step 2 — The atomic move (create app + plugins, migrate all code, delete the flat layout)

*Per D1 (lean atomic): one big, self-contained step. Substeps may transiently break imports; the
step ends green. No shims — the flat modules are deleted here, not bridged.*

### 2a — Plugin distributions
- [ ] 2.1 Create `packages/coral-plugin-math/` — `pyproject.toml` (hatchling; `name =
      "coral-plugin-math"`; `dependencies = ["coral-core"]`; entry point
      `[project.entry-points."coral.plugins"] math = "coral_plugin_math:MathPlugin"`) and
      `src/coral_plugin_math/__init__.py` holding the real functions + `Calculator` and a
      `MathPlugin(Plugin)` whose `get_functions()` / `get_classes()` return today's math dicts.
- [ ] 2.2 Same for `coral-plugin-string` (`StringProcessor`, `print_result`, `StringPlugin`,
      entry-point `string`).
- [ ] 2.3 Same for `coral-plugin-phiflow` (wrappers, `PhiFlowPlugin`, entry-point `phiflow`;
      `dependencies = ["coral-core", "phiflow", "jax", "h5py"]`). *(D5)* Drop the `AVAILABLE`
      try/except guard — installing the plugin guarantees the deps; a broken import fails loud.

### 2b — Host distribution
- [ ] 2.4 Create `packages/coral-app/` — `pyproject.toml` (hatchling; `name = "coral-app"`;
      `dependencies = ["coral-core"]`; project metadata migrated from the old root; *(D6)*
      `[project.scripts] coral = "coral_app.cli:main"`; wheel target `src/coral_app`). Remove the
      migrated metadata (and `[tool.uv] package = false`) from the root `pyproject.toml`.
- [ ] 2.5 Move `executor.py`, `registry.py` into `src/coral_app/` **bodies unchanged** (only their
      `definitions` imports are repointed in 2.7); move `main.py`'s logic into `src/coral_app/cli.py`.
- [ ] 2.6 Move `PRIMITIVES_MAP` into the host (`src/coral_app/primitives.py`).
- [ ] 2.7 Add `src/coral_app/__init__.py` with the host API: `PLUGIN_GROUP = "coral.plugins"`,
      `discover()`, `load(name)`, `load_all(names)` (skeleton semantics), plus
      `build_function_map(include=..., exclude=...)` / `build_class_map(...)` **with the same
      signatures as today**, re-implemented over `discover`/`load`, merging in `include` order
      (empty/`None` → `sorted(discover())`). *(D4)* Unknown/not-discoverable name → `LookupError`
      (fail-loud, aborts). Repoint `coral_app.registry` / `coral_app.executor` at these + the host
      `PRIMITIVES_MAP`.

### 2c — Cutover & cleanup (same step)
- [ ] 2.8 *(D7)* Update all tests to import from `coral_app.*` / `coral_core.*`; drop
      `from executor import` / `from registry import` / `from definitions import`.
- [ ] 2.9 Delete the flat layout: root `executor.py`, `registry.py`, `main.py`, and the entire
      `definitions/` package. *(D8)* Apply straggler decisions (delete stale `registry-py.json`).
- [ ] 2.10 *(D6)* Update `coral-py` to launch the `coral` console script via
      `uv run --quiet --project "$HERE" coral "$@"` (no `cd`); verify `register` writes
      `node_types.json` into the **caller's** cwd and `run` executes.
- [ ] 2.11 `uv sync` — verify all four packages install editable and the plugins register their entry
      points (`python -c "from importlib.metadata import entry_points as e; print(sorted(x.name for x in e(group='coral.plugins')))"`
      → `['math', 'phiflow', 'string']`).
- [ ] 2.12 **Parity gate:** registry output via the new host equals the Step-0 golden files
      byte-for-byte for `math`, `string`, `phiflow`, all; characterization `run` results unchanged.
- [ ] 2.13 `uv sync && uv run pytest` → all green (baseline count + core tests, all migrated).
- [ ] 2.14 Manual smoke through the launcher from a scratch cwd: `./coral-py -p "math" register` and
      `./coral-py -p "math" run <graph>` behave as before.

## Step 3 — Acceptance matrix + packaging verification (the skeleton's §8, coral-flavored)

- [ ] 3.1 Add `tests/test_plugin_discovery.py`:
      - `discover()` lists installed plugin names **without importing** them (assert the plugin
        modules are absent from `sys.modules` before `load`).
      - `load("bogus")` → `LookupError`; an entry point resolving to a non-`Plugin` → `TypeError`.
      - *(D4)* `register` / host `build_*_map` with an unknown `-p` name → `LookupError` (fail-loud).
      - **Laziness:** `load("math")` must not import `coral_plugin_phiflow`
        (`assert "coral_plugin_phiflow" not in sys.modules`).
- [ ] 3.2 Add a host-only registry test: with **no** plugin selected, `register` emits **only** the
      primitives (six entries) — proving the host works with zero function/class plugins.
- [ ] 3.3 Add a "plugin adds nodes" test: selecting `math` makes the math functions/`Calculator`
      nodes appear in the registry.
- [ ] 3.4 Wheel/pip acceptance (the faithful end-user path): `uv build --all-packages --wheel`, then
      in a **clean** venv `pip install --find-links dist coral-app` (list = only primitives),
      `+ coral-plugin-math`, `+ coral-plugin-phiflow`, uninstall one, and re-run the laziness check.
      *(Scripted, not necessarily in the pytest run — decide with D7 whether to gate it in CI.)*
- [ ] 3.5 `uv run pytest` → all green.

## Step 4 — Documentation

- [ ] 4.1 Update `README.md`: setup (`uv sync` over the workspace), the `coral` console script /
      `coral-py`, install-a-plugin story.
- [ ] 4.2 Update `CLAUDE.md`: the new package layout, entry-point discovery, `Plugin` ABC, where
      `PRIMITIVES_MAP` lives.
- [ ] 4.3 Update `docs/ONBOARDING.md` (+ `docs/ONBOARDING.it.md`): replace the `definitions/` +
      `_MODULES` narrative with the core/app/plugin + entry-point architecture; refresh the
      "add a new library (Persona A)" steps to "create a new plugin distribution"; update the
      strengths/weaknesses (import-time cost and convention-not-contract are now resolved).
- [ ] 4.4 Remove `definitions/README.md` with the `definitions/` package (relocate any still-useful
      content into the relevant package README).

---

## Contract-preservation checklist (verify at Steps 2 and 3)

- [ ] `node_types.json` byte-identical to Step-0 goldens for `math`, `string`, `phiflow`, all.
- [ ] `-p` semantics unchanged: comma-separated names; empty → all discovered.
- [ ] Merge order deterministic; the `print_result` duplicate (math + string) still resolves
      later-wins with no error.
- [ ] `run` results and stdout unchanged for the characterization graphs.
- [ ] `coral-py` writes `node_types.json` into the caller's cwd; `--touch-dir` still accepted
      (still a no-op).

## Rollback

Each top-level step is a coherent, green commit on `16-plugin-modularization`. If a step regresses,
revert that commit; earlier steps remain green and shippable.
