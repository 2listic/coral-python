# TODO: the wheel acceptance test failed once with a stale `coral-core`

Found while running the slow lane after implementing this issue (2026-10-07). Not fixed, and not
fully explained. Everything known so far is below.

## Symptom

`uv run pytest -m slow` → 8 passed, **1 failed**: `tests/test_acceptance.py::test_wheel_pip_acceptance`.
The pip-installed `coral` console script crashed at import:

```
File ".../pytest-of-matteo/pytest-30/test_wheel_pip_acceptance0/venv/bin/coral", line 4
  from coral_app.cli import main
File ".../site-packages/coral_app/nodeports.py", line 19, in <module>
  from coral_core import output_names
ImportError: cannot import name 'output_names' from 'coral_core'
  (.../pytest-30/test_wheel_pip_acceptance0/venv/lib/python3.14/site-packages/coral_core/__init__.py)
```

So the throwaway venv received the **new** `coral-app` (it imports `output_names`) next to an **old**
`coral-core` (from before this issue's Step 1, which added `outputs` / `output_names`).

## How the test installs (the relevant code)

`tests/test_acceptance.py`:

- the `wheelhouse` fixture runs `uv build --all-packages --wheel --out-dir <tmp_path_factory "wheelhouse">`,
  i.e. `/tmp/pytest-of-matteo/pytest-<N>/wheelhouse0/`;
- `_CleanEnv.install(*packages)` (around lines 88–111) runs
  `uv pip install --python <venv> --find-links <wheelhouse> --refresh-package <p> ... <packages>`,
  with `--refresh-package` **only for the packages named in the call**;
- the test calls `install("coral-app")`, `install("coral-plugin-math")`,
  `install("coral-plugin-phiflow")`. **`coral-core` is never named**, so it is never refreshed: it
  arrives only as a dependency.
- Every workspace package's version is static (`coral-core` 0.0.0, `coral-app` 0.1.0), while the
  content changes. The docstring of `install()` already describes this trap for the named packages.

This issue is the first change to `coral-core`'s *code* since that refresh logic was written, which
is why the gap had never shown.

## What was verified

- Neither `coral-core` nor `coral-app` exists on PyPI (`https://pypi.org/pypi/<name>/json` → 404).
  The old `coral-core` therefore came from **uv's local cache**.
- After the failure, a scratchpad install ran with `--refresh-package coral-core`. It probably
  replaced the cached `coral-core`, so the original condition was destroyed before it was
  understood.
- Re-runs right after that: 1 pass, **2 fails in ~0.5s**, then 9 passes in a row. **The output of the
  two fast failures was never captured** (it was piped through `tail -1`). Their cause is unknown;
  they may or may not be the same problem.
- `uv cache clean coral-core coral-app coral-plugin-math coral-plugin-phiflow coral-plugin-string
  coral-plugin-pypde` (local packages only, so the jax stack stays cached), then 4 runs: 4 passes.
- **Hypothesis "stale name+version is enough" — refuted.** A `coral-core` 0.0.0 built from commit
  `0b1ac9f` (before Step 1; `git archive 0b1ac9f coral-core | tar -x`, then `uv build --wheel`) was
  installed into a scratchpad venv via `--find-links <scratch dist>`, to seed uv's cache. The
  acceptance test then **passed** twice. So the stale wheel is not picked up by name+version alone.
- **State left behind:** that seeding put the **old** `coral-core` (no `outputs` / `output_names`) into
  uv's cache, and it was **not** removed when the session ended. If the acceptance test fails
  tomorrow, this seed is a suspect before anything else. Run
  `uv cache clean coral-core` first to start from a known state, unless step 1 below deliberately
  wants a seeded cache.

## Open hypothesis: the cache key includes the wheel's path

pytest numbers its base temp directories upward (`pytest-50`, `-51`, …) and keeps the last three.
`/tmp` is wiped on reboot, so after a reboot the numbering **restarts from 0**. The failing run was
`pytest-30`. If uv keys a `--find-links` wheel by path (plus name/version), a run in a previous boot
could have cached the old `coral-core` at
`/tmp/pytest-of-matteo/pytest-30/wheelhouse0/coral_core-0.0.0-py3-none-any.whl`, and today's run,
reaching `pytest-30` again, was served it, because nothing refreshes `coral-core`.

## Next steps

1. **Test the path hypothesis.** `ls -d /tmp/pytest-of-matteo/pytest-*` to find the highest N; the
   next run uses N+1. Build the pre-change `coral-core` as above, copy the wheel to
   `/tmp/pytest-of-matteo/pytest-<N+1>/wheelhouse0/`, `uv pip install` it into a scratch venv with
   `--find-links` that directory (this seeds the cache under that path), **delete
   `pytest-<N+1>`** (otherwise pytest skips that number), then run the acceptance test. A failure
   with the `ImportError` above confirms the hypothesis.
2. **Always capture output to a file** (`> file 2>&1`), never through `| tail`: the two fast failures
   were lost that way.
3. If the fast failures recur, read the captured file: `_run()` captures each step's output, so the
   failing `uv` command and its stderr are in the report.
4. **Fix**, whatever the exact key turns out to be: make `install()` refresh every workspace
   package, not only the named ones, so a dependency is never served stale. The list can be
   derived the way `tests/invariants/test_source_rules.py` finds every distribution (each directory
   with a `pyproject.toml`), or written out. Decide which, then show the diff before applying it.
5. Run `uv run pytest -m slow` (output to a file) and confirm the full slow lane passes.

## Commands

```bash
# the failing test alone (~1–3s with a warm cache; ~250s if PyPI has a newer jax than the pin)
uv run pytest -q tests/test_acceptance.py > /tmp/acc.txt 2>&1; tail -1 /tmp/acc.txt

# the whole slow lane
uv run pytest -m slow > /tmp/slow.txt 2>&1; tail -1 /tmp/slow.txt

# reset only the local packages in uv's cache (keeps jax & co.)
uv cache clean coral-core coral-app coral-plugin-math coral-plugin-phiflow coral-plugin-string coral-plugin-pypde
```
