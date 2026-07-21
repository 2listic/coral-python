"""Golden-file contract tests (issue #16, decision D2).

Pin the ``register`` output (``node_types.json``) byte-for-byte for each module set. The golden files
under ``tests/golden/`` are a lasting regression guard: they were snapshotted from the pre-refactor
flat code, and asserting equality here proves the plugin-modularization move preserves the registry
contract the DealiiX platform consumes. An *intentional* change to a plugin's surface requires
regenerating the affected golden (a reviewable diff), which is the point.

These tests exercise the real ``save_registry_to_file`` code path, so they hold across the atomic
move — only their imports are repointed to ``coral_app`` when the flat modules are deleted.
"""

from pathlib import Path

import pytest

from registry import save_registry_to_file
from definitions import AVAILABLE_MODULES

GOLDEN_DIR = Path(__file__).parent / "golden"

# Each case: (golden filename stem, module list passed to save_registry_to_file).
# "all" mirrors the CLI's empty -p, which resolves to every available module in registration order.
GOLDEN_CASES = {
    "math": ["math"],
    "string": ["string"],
    "phiflow": ["phiflow"],
    "all": list(AVAILABLE_MODULES),
}


@pytest.mark.parametrize("name,modules", list(GOLDEN_CASES.items()))
def test_registry_matches_golden(name, modules, tmp_path):
    """Registry output is byte-identical to the recorded golden.

    GIVEN a recorded golden ``node_types.<set>.json`` for a module set,
    WHEN ``save_registry_to_file`` regenerates the registry for that same set,
    THEN the emitted file is byte-for-byte identical to the golden.
    """
    golden = GOLDEN_DIR / f"node_types.{name}.json"
    assert golden.exists(), f"missing golden file: {golden}"

    out = tmp_path / f"node_types.{name}.json"
    save_registry_to_file(str(out), modules=modules)

    assert out.read_bytes() == golden.read_bytes(), (
        f"registry output for modules={modules} diverged from {golden.name}"
    )
