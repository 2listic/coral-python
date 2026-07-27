# pyplug — Reconstruction Spec (handoff)

**Audience:** an AI agent, in a fresh context, tasked with building the
full-fledged application on top of this plugin architecture.

**The one rule that governs everything below:**

> The **structure** of this skeleton — packaging, discovery, lazy loading,
> host/plugin separation, build and install flow — is the **invariant** and
> MUST be reconstructed exactly. The **contract interface** — the concrete
> methods a plugin exposes (`name`, `describe`) — is a **placeholder**. The
> full-fledged app WILL replace those methods with its real surface. Change
> the interface; keep the structure.

This document is self-contained: it embeds the code and configuration needed to
rebuild the skeleton without access to the original repo.

---

## 1. What the skeleton proves

A host program that, given plugin names **at runtime**, discovers and lazily
loads plugins that were unknown in advance (including third-party ones), and
holds them as live, decoupled objects that expose their functions and classes
through a shared contract. The skeleton stops there; what a plugin's exposed
items *do*, and how the host consumes them, is the full-fledged app's job.

---

## 2. Fixed vs. variable

**FIXED — reconstruct exactly (the structure):**
- 4 independently installable distributions in one monorepo; strict dependency
  direction.
- Contract lives in its own package (`pyplug-core`) as an **ABC**.
- Discovery via stdlib `importlib.metadata` **entry points**, group
  `pyplug.plugins`; entry point points to the plugin **class**.
- **Lazy**: enumerate without importing; import/instantiate only requested names.
- Host never imports plugins; plugins never import the host.
- Toolchain: hatchling build backend, uv workspace for dev, pip + wheel index
  for the end-user path, Python floor 3.12.

**VARIABLE — expected to change in the full-fledged app (the interface):**
- The concrete methods on the contract ABC. Here they are `name` + `describe()`,
  chosen only to demonstrate loading and access. Replace them with the real
  surface (whatever the larger app needs a plugin to expose). The *fact* that
  the contract is an ABC in `pyplug-core`, subclassed by plugins, does not change.
- Whatever the host does with loaded plugins after `load()` returns.
- How the host instantiates the plugin class — today `PluginClass()` with no
  args; a real app may pass a host-provided context object at that point.

---

## 3. Repository layout

Monorepo, `src/` layout, 4 packages each with its own `pyproject.toml`:

```
pyplug/
├── pyproject.toml                         # uv workspace root (virtual)
└── packages/
    ├── pyplug-core/
    │   ├── pyproject.toml
    │   └── src/pyplug_core/__init__.py
    ├── pyplug-app/
    │   ├── pyproject.toml
    │   └── src/pyplug_app/
    │       ├── __init__.py
    │       └── cli.py
    ├── pyplug-example-a/
    │   ├── pyproject.toml
    │   └── src/pyplug_example_a/__init__.py
    └── pyplug-example-b/
        ├── pyproject.toml
        └── src/pyplug_example_b/__init__.py
```

Distribution → import name: `pyplug-core`→`pyplug_core`,
`pyplug-app`→`pyplug_app`, `pyplug-example-a`→`pyplug_example_a`,
`pyplug-example-b`→`pyplug_example_b`.

**Dependency rules (MUST hold):**
- `pyplug-core` depends on nothing internal.
- `pyplug-app` depends on `pyplug-core` only.
- Each plugin depends on `pyplug-core` **and only core** — a plugin MUST NOT
  import or depend on `pyplug-app`. This enforced separation is what proves the
  contract is genuinely decoupled.
- The host MUST NOT import the plugins; it finds them at runtime via discovery.

Two example plugins exist to exercise the multi-plugin path and the
install/uninstall matrix.

---

## 4. The contract — `pyplug-core` (VARIABLE interface, FIXED shape)

`packages/pyplug-core/src/pyplug_core/__init__.py`:

```python
"""pyplug-core — the shared contract for the pyplug plugin system."""

from abc import ABC, abstractmethod

__all__ = ["Plugin"]


class Plugin(ABC):
    """Contract a plugin subclasses to expose itself to the host."""

    @property
    @abstractmethod
    def name(self) -> str:
        """A short, stable identifier for the plugin."""

    @abstractmethod
    def describe(self) -> str:
        """A human-readable description of what the plugin provides."""
```

`packages/pyplug-core/pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pyplug-core"
version = "0.0.0"
description = "The shared contract for the pyplug plugin system."
requires-python = ">=3.12"
dependencies = []

[tool.hatch.build.targets.wheel]
packages = ["src/pyplug_core"]
```

> **For the full-fledged app:** replace `name`/`describe` with the real
> abstract methods. Keep it an ABC in this package with `@abstractmethod` so the
> contract is *enforced*, not duck-typed. Once real plugins exist, this package's
> surface and the entry-point group name (§5) are **public API** — treat as stable.

---

## 5. Discovery & loading — `pyplug-app` (FIXED)

`packages/pyplug-app/src/pyplug_app/__init__.py`:

```python
"""pyplug-app — the host that discovers, loads, and holds plugins."""

from importlib.metadata import entry_points

from pyplug_core import Plugin

__all__ = ["PLUGIN_GROUP", "discover", "load", "load_all"]

#: The entry-point group plugins declare themselves under. Public API; stable.
PLUGIN_GROUP = "pyplug.plugins"


def discover() -> list[str]:
    """Return the names of all installed plugins, without importing any."""
    return sorted(ep.name for ep in entry_points(group=PLUGIN_GROUP))


def load(name: str) -> Plugin:
    """Import, instantiate, and return the plugin registered under ``name``."""
    matches = entry_points(group=PLUGIN_GROUP, name=name)
    if not matches:
        raise LookupError(
            f"no plugin registered under {name!r} in group {PLUGIN_GROUP!r}"
        )
    ep = next(iter(matches))
    plugin_cls = ep.load()
    if not (isinstance(plugin_cls, type) and issubclass(plugin_cls, Plugin)):
        raise TypeError(
            f"plugin {name!r} resolved to {plugin_cls!r}, "
            "which is not a pyplug_core.Plugin subclass"
        )
    return plugin_cls()


def load_all(names: list[str]) -> list[Plugin]:
    """Load several plugins by name, preserving the order given."""
    return [load(name) for name in names]
```

**Semantics that MUST hold:**
- `discover()` enumerates entry points **without importing** any plugin module.
- `load()` imports only the requested plugin, validates it resolves to a
  `Plugin` subclass (`TypeError` otherwise), and instantiates it. Unknown name →
  `LookupError`.
- The entry point resolves to the plugin **class**; the host instantiates it
  (`plugin_cls()`), which is where a real app may later inject host context.
- Multiple plugins can be loaded at once.

`packages/pyplug-app/src/pyplug_app/cli.py`:

```python
"""Command-line interface for pyplug."""

import argparse
import sys

from pyplug_app import discover, load


def _cmd_list(_: argparse.Namespace) -> int:
    names = discover()
    if not names:
        print("no plugins installed")
        return 0
    for name in names:
        print(name)
    return 0


def _cmd_describe(args: argparse.Namespace) -> int:
    status = 0
    for name in args.names:
        try:
            plugin = load(name)
        except (LookupError, TypeError) as exc:
            print(f"{name}: {exc}", file=sys.stderr)
            status = 1
            continue
        print(f"{plugin.name}: {plugin.describe()}")
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pyplug", description="pyplug plugin host")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="list installed plugins (no import)")
    p_list.set_defaults(func=_cmd_list)

    p_desc = sub.add_parser(
        "describe", help="load plugins and print their names and descriptions"
    )
    p_desc.add_argument(
        "names", nargs="+", metavar="NAME", help="plugin name(s) to describe"
    )
    p_desc.set_defaults(func=_cmd_describe)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
```

`packages/pyplug-app/pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pyplug-app"
version = "0.0.0"
description = "The pyplug host: discovers, loads, and holds plugins. Provides the CLI and Python API."
requires-python = ">=3.12"
dependencies = ["pyplug-core"]

[project.scripts]
pyplug = "pyplug_app.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/pyplug_app"]
```

> **For the full-fledged app:** the CLI commands (`list`, `describe`) and the
> API surface will grow/change alongside the new contract interface. The
> discovery internals — `entry_points(group=PLUGIN_GROUP)`, lazy `ep.load()`,
> subclass validation, instantiate-the-class — are structural and stay.

---

## 6. Example plugins (FIXED shape, VARIABLE body)

Each plugin subclasses the contract and declares an entry point under
`pyplug.plugins` pointing at its class.

`packages/pyplug-example-a/src/pyplug_example_a/__init__.py`:

```python
"""pyplug-example-a — an example plugin demonstrating the pyplug contract."""

from pyplug_core import Plugin

__all__ = ["PluginA"]


class PluginA(Plugin):
    """A minimal example plugin."""

    @property
    def name(self) -> str:
        return "example_a"

    def describe(self) -> str:
        return "Example plugin A — depends only on pyplug-core."
```

`packages/pyplug-example-a/pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pyplug-example-a"
version = "0.0.0"
description = "Example pyplug plugin A."
requires-python = ">=3.12"
dependencies = ["pyplug-core"]

[project.entry-points."pyplug.plugins"]
example_a = "pyplug_example_a:PluginA"

[tool.hatch.build.targets.wheel]
packages = ["src/pyplug_example_a"]
```

`pyplug-example-b` is identical with `a`→`b`, `A`→`B`, entry point
`example_b = "pyplug_example_b:PluginB"`.

> The `X = "module:Class"` entry-point line is the structural handshake — it is
> how a plugin declares itself at install time and how the host finds it at
> runtime. This form stays regardless of what the contract methods become.

---

## 7. Workspace root & toolchain (FIXED)

Root `pyproject.toml` (virtual workspace root — no `[project]`; dev/uv-only,
never read by pip, never baked into wheels):

```toml
[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
pyplug-core = { workspace = true }
pyplug-app = { workspace = true }
pyplug-example-a = { workspace = true }
pyplug-example-b = { workspace = true }
```

- **Build backend:** `hatchling` (every package) → standard PEP 517/621 wheels.
- **Dev front-end:** `uv` workspace. `uv sync` installs all four editable and
  cross-linked. `uv build --all-packages --wheel` builds every package into
  `dist/`.
- **End-user path:** `pip`. `dist/` is used as a local index via `--find-links`.
  pip never reads uv config; the uv layer is invisible to end users.
- **Python floor:** 3.12 (uniform). No `from __future__ import annotations` —
  unnecessary on a 3.12 floor.

---

## 8. Build, install, and the acceptance test (FIXED)

Build all wheels:

```sh
uv build --all-packages --wheel      # -> dist/*.whl
```

End-user install (pip resolves dependencies from the local wheel index;
`pyplug-core` arrives automatically as a dependency of `pyplug-app`):

```sh
pip install --find-links dist pyplug-app          # host only
pip install --find-links dist pyplug-example-a    # add a plugin, by name
```

`--find-links dist` is required because the packages are not on any real index;
it tells pip to resolve names from the local wheels. (No `--no-index`: allowing
PyPI fallback keeps the sim faithful and robust to future third-party deps.)

**Acceptance matrix — the skeleton is correct iff all pass** (clean venv):

1. `pip install --find-links dist pyplug-app` → `pyplug list` prints
   `no plugins installed`.
2. `+ pyplug-example-a` → `pyplug list` prints `example_a`.
3. `+ pyplug-example-b` → `pyplug list` prints `example_a` and `example_b`;
   `pyplug describe example_a example_b` prints both names + descriptions.
4. `pip uninstall -y pyplug-example-b` → `pyplug list` prints `example_a` only.
5. **Laziness:** with A and B both installed, loading only A must not import B:
   ```sh
   python -c "import sys, pyplug_app; pyplug_app.load('example_a'); \
   assert 'pyplug_example_b' not in sys.modules, 'B was imported'; print('lazy: OK')"
   ```

---

## 9. Decision log — do NOT reintroduce rejected approaches

- **Discovery = entry points**, not path-scanning + `inspect`, not
  namespace-package scanning, not `pluggy`/`stevedore` (which merely wrap entry
  points). Rendezvous is one-directional: the host reads standard metadata; a
  plugin MUST NOT write host-owned files or run post-install hooks.
- **Contract = ABC**, not `typing.Protocol` (no enforcement) and not a bare
  `register()` hook. Entry point → **class**, not an instance.
- **`[tool.uv.sources]` in the root** is the canonical uv way to cross-link the
  local packages in dev. It is dev/uv-only and NOT baked into wheels, so the pip
  end-user path is unaffected. Do NOT use `file://` path dependencies in a
  package's `dependencies` — that hardcodes paths and poisons the real wheel.
- **Guiding principle:** canonical & robust over clever; prefer stdlib and
  standard packaging. Separation is structural (package/dependency boundaries),
  not by convention.
