"""Golden-file contract tests (issue #16, decision D2).

Pin the ``register`` output (``node_types.json``) byte-for-byte for each module set. The golden files
under ``tests/golden/`` are a lasting regression guard: they were snapshotted from the pre-refactor
flat code, and asserting equality here proves the plugin-modularization move preserves the registry
contract the DealiiX platform consumes. An *intentional* change to a plugin's surface requires
regenerating the affected golden (a reviewable diff), which is the point.

These tests exercise the real ``save_registry_to_file`` code path, so they hold across the atomic
move — their imports are repointed to ``coral_app`` now that the flat modules are deleted.

Parity granularity (issue #16): the single-module goldens (``math``/``string``/``phiflow``) are
asserted **byte-for-byte** — order within one plugin is stable. The ``all`` golden is asserted by
**content** (parsed dicts, order-insensitive): with entry-point discovery the "all" default is now
``sorted(discover())``, which reorders only the cross-module class entries (``StringProcessor``
moves after the PhiFlow classes). That reorder is functionally irrelevant — the platform reads the
registry as a lookup keyed by ``type`` — so it is not treated as a regression, while any real
change in entries or values is still caught.
"""

import json
from pathlib import Path

import pytest

from coral_app import discover
from coral_app.registry import save_registry_to_file

GOLDEN_DIR = Path(__file__).parent / "golden"

# Each case: (golden filename stem, module list passed to save_registry_to_file).
# "all" mirrors the CLI's empty -p, which resolves to every installed plugin via discover().
GOLDEN_CASES = {
    "math": ["math"],
    "string": ["string"],
    "phiflow": ["phiflow"],
    "all": discover(),
}


@pytest.mark.parametrize("name", [
    pytest.param("math", marks=pytest.mark.math),
    pytest.param("string", marks=pytest.mark.string),
    pytest.param("phiflow", marks=pytest.mark.phiflow),
])
def test_single_module_registry_matches_golden_bytes(name, tmp_path):
    """Single-module registry output is byte-identical to the recorded golden.

    GIVEN a recorded golden ``node_types.<module>.json`` for one plugin,
    WHEN ``save_registry_to_file`` regenerates the registry for that plugin,
    THEN the emitted file is byte-for-byte identical to the golden.
    """
    modules = GOLDEN_CASES[name]
    golden = GOLDEN_DIR / f"node_types.{name}.json"
    assert golden.exists(), f"missing golden file: {golden}"

    out = tmp_path / f"node_types.{name}.json"
    save_registry_to_file(str(out), modules=modules)

    assert out.read_bytes() == golden.read_bytes(), (
        f"registry output for modules={modules} diverged from {golden.name}"
    )


@pytest.mark.math
@pytest.mark.string
@pytest.mark.phiflow
def test_all_modules_registry_matches_golden_content(tmp_path):
    """All-modules registry has the same entries and values as the recorded golden.

    GIVEN the recorded ``node_types.all.json`` golden,
    WHEN ``save_registry_to_file`` regenerates the registry for every discovered plugin,
    THEN the emitted registry equals the golden as parsed content (order-insensitive) — sorted
         discovery reorders only cross-module class keys, which the platform's keyed lookup ignores.
    """
    golden = GOLDEN_DIR / "node_types.all.json"
    assert golden.exists(), f"missing golden file: {golden}"

    out = tmp_path / "node_types.all.json"
    save_registry_to_file(str(out), modules=GOLDEN_CASES["all"])

    generated = json.loads(out.read_text())
    expected = json.loads(golden.read_text())
    assert generated == expected, "all-modules registry content diverged from node_types.all.json"
