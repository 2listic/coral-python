"""Constants this package's tests share, in a module with a name no other package uses.

Why not ``conftest.py``: with ``--import-mode=importlib`` a test module doing ``from conftest import X``
goes through the normal import system, where the module name ``conftest`` is global — so the four
packages' conftests would resolve to whichever was imported first. pytest handles its *own* conftest
loading correctly; a plain import of it does not. Anything needed at **collection** time (a path to
parametrise graph files over) cannot be a fixture, so it lives here instead.
"""

from importlib.metadata import entry_points
from pathlib import Path

import pytest

#: This plugin's entry-point name — its identity to the host and to the platform's `-p` option. Written
#: by hand: the rule against a hardcoded plugin catalog forbids one place listing which plugins *exist*,
#: and this is a self-reference inside the package that declares the name in its own pyproject.toml.
#: Deriving it from installed metadata would silently follow a rename, destroying the one assertion
#: worth having — `phiflow` is what the DealiiX platform's `-p` contract names.
PLUGIN_NAME = "phiflow"

#: The entry-point group every coral plugin registers under.
PLUGIN_GROUP = "coral.plugins"

#: The import package this distribution ships. Used to ask metadata the *reverse* question — "under what
#: name is this package registered?" — which is what catches a typo in ``PLUGIN_NAME``.
MODULE_NAME = "coral_plugin_phiflow"

#: Whether *this* plugin is installed in the environment under test.
INSTALLED = bool(entry_points(group=PLUGIN_GROUP, name=PLUGIN_NAME))

#: Skip decorator for the one module collected even when the plugin is absent.
requires_this_plugin = pytest.mark.skipif(
    not INSTALLED, reason=f"plugin {PLUGIN_NAME!r} not installed"
)

#: The graphs this plugin owns: three real editor exports, the largest being 33 nodes / 45 edges.
GRAPHS = Path(__file__).parent / "graphs"

#: The user-facing examples this plugin ships — `coral run examples/phiflow/...` in the docs.
EXAMPLES = Path(__file__).parent.parent / "examples"

#: This plugin's recorded ``node_types.json`` slice.
GOLDEN = Path(__file__).parent / "system" / "golden" / f"node_types.{PLUGIN_NAME}.json"
