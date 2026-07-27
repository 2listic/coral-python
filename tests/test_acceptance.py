"""Wheel/pip acceptance for the plugin modularization (issue #16, Step 3.4).

The faithful end-user path, exercised end to end: build every workspace package into a wheel, then in
a **clean** venv install them incrementally and prove the modularization's runtime promises hold when
the packages are consumed as *installed distributions* (not the editable workspace the other tests
use):

* ``coral-app`` alone is a working host          -> the registry has only the 6 primitives;
* installing a plugin adds its nodes             -> ``+coral-plugin-math`` brings ``add``/``Calculator``;
* plugins compose                                -> ``+coral-plugin-phiflow`` brings ``phiflow`` too;
* discovery/load stay lazy                       -> ``load("math")`` never imports ``coral_plugin_phiflow``;
* uninstalling a plugin removes its nodes        -> ``phiflow`` disappears from discovery.

This is the one heavy test (``uv build`` + a throwaway venv + installs), so it is marked ``slow``:
it runs with a plain ``pytest`` but can be skipped with ``-m "not slow"``. ``uv`` is used for the venv
and installs so the phiflow stack (jax/h5py/phiflow) resolves from uv's existing cache instead of
re-downloading from PyPI on every run. Skipped if ``uv`` is not on PATH.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow

UV = shutil.which("uv")


class AcceptanceCommandError(subprocess.CalledProcessError):
    """A subprocess step in the acceptance run exited non-zero.

    Subclasses ``CalledProcessError`` so callers keep its getters — ``cmd``, ``returncode``,
    ``stdout``, ``stderr`` — for free. Only ``__str__`` is widened: the base class omits stderr,
    which is exactly the output that explains a failed ``uv``/``pip`` step.
    """

    def __str__(self) -> str:
        return (
            f"{' '.join(map(str, self.cmd))} exited {self.returncode}\n"
            f"--- stdout ---\n{self.stdout}\n--- stderr ---\n{self.stderr}"
        )


def _run(cmd, **kwargs) -> subprocess.CompletedProcess:
    """Run a command capturing output; raise :class:`AcceptanceCommandError` on non-zero exit."""
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        raise AcceptanceCommandError(result.returncode, cmd, result.stdout, result.stderr)
    return result


@pytest.fixture(scope="module")
def wheelhouse(project_root: Path, tmp_path_factory) -> Path:
    """Build every workspace package into wheels once, return the dist directory.

    GIVEN the uv workspace, WHEN ``uv build --all-packages --wheel`` runs, THEN a dist directory
    holding one wheel per package is produced for the clean-venv installs below.
    """
    if UV is None:
        pytest.skip("uv not available on PATH")
    dist = tmp_path_factory.mktemp("wheelhouse")
    _run(
        [UV, "build", "--all-packages", "--wheel", "--out-dir", str(dist)],
        cwd=project_root,
    )
    wheels = list(dist.glob("*.whl"))
    assert wheels, "uv build produced no wheels"
    return dist


class _CleanEnv:
    """A throwaway venv into which wheels are pip-installed and queried."""

    def __init__(self, venv_dir: Path, dist: Path):
        self.venv_dir = venv_dir
        self.dist = dist
        self.python = venv_dir / "bin" / "python"
        self.coral = venv_dir / "bin" / "coral"

    def install(self, *packages: str) -> None:
        """Install packages from the local wheelhouse (heavy deps come from uv's cache)."""
        _run([UV, "pip", "install", "--python", str(self.python),
              "--find-links", str(self.dist), *packages])

    def uninstall(self, *packages: str) -> None:
        _run([UV, "pip", "uninstall", "--python", str(self.python), *packages])

    def py(self, code: str) -> str:
        """Run a snippet in the venv's interpreter, return its stdout (raises on error)."""
        return _run([str(self.python), "-c", code]).stdout.strip()

    def discovered(self) -> list:
        """The sorted plugin names the installed host discovers."""
        out = self.py("from coral_app import discover; print('\\n'.join(discover()))")
        return out.split("\n") if out else []

    def registry(self, tmp: Path) -> dict:
        """Generate the all-plugins registry via the `coral` console script and load it."""
        out = tmp / "node_types.json"
        _run([str(self.coral), "register", f"--output={out}"])
        return json.loads(out.read_text())


@pytest.fixture
def clean_env(wheelhouse: Path, tmp_path: Path) -> _CleanEnv:
    """Create a fresh, isolated venv (no site packages) for one acceptance run."""
    venv_dir = tmp_path / "venv"
    # Base the venv on the interpreter running the suite (the workspace's Python): it satisfies the
    # packages' `requires-python >=3.12`, unlike whatever bare `uv venv` might pick as the default.
    _run([UV, "venv", "--python", sys.executable, str(venv_dir)])
    return _CleanEnv(venv_dir, wheelhouse)


def test_wheel_pip_acceptance(clean_env: _CleanEnv, tmp_path: Path):
    """GIVEN wheels for the host and every plugin,
    WHEN they are pip-installed one at a time into a clean venv,
    THEN the host works alone (primitives only), each plugin adds exactly its own nodes, load stays
         lazy across plugins, and uninstalling a plugin removes its nodes.
    """
    env = clean_env

    # Host alone: a complete program with zero function/class plugins -> only the 6 primitives.
    env.install("coral-app")
    assert env.discovered() == []
    host_registry = env.registry(tmp_path)
    assert len(host_registry) == 6
    assert all(e["node_type"] == "primitive" for e in host_registry.values())

    # + math: its function and constructor nodes appear.
    env.install("coral-plugin-math")
    assert env.discovered() == ["math"]
    with_math = env.registry(tmp_path)
    assert with_math["add"]["node_type"] == "function"
    assert with_math["Calculator"]["node_type"] == "constructor"

    # + phiflow: plugins compose; both are discovered.
    env.install("coral-plugin-phiflow")
    assert env.discovered() == ["math", "phiflow"]

    # Laziness: loading math must not import the phiflow plugin module.
    env.py(
        "import sys\n"
        "from coral_app import load\n"
        "load('math')\n"
        "assert 'coral_plugin_math' in sys.modules, 'load(math) did not import math'\n"
        "assert 'coral_plugin_phiflow' not in sys.modules, 'load(math) imported phiflow'\n"
    )

    # Uninstall phiflow: it disappears from discovery, math remains.
    env.uninstall("coral-plugin-phiflow")
    assert env.discovered() == ["math"]
