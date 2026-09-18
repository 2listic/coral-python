"""Constants this package's tests share, in a module with a name no other package uses.

Why not ``conftest.py``: with ``--import-mode=importlib`` a test module doing ``from conftest
import X`` goes through the normal import system, where the module name ``conftest`` is global, so
the packages' conftests would resolve to whichever was imported first. Anything needed at
**collection** time — a path to parametrise graph files over — cannot be a fixture, so it lives here.
"""

from importlib.metadata import entry_points
from pathlib import Path

import pytest

#: This plugin's entry-point name — its identity to the host and to the platform's `-p` option.
#: Written by hand: derived from installed metadata it would silently follow a rename, destroying
#: the one assertion worth having.
PLUGIN_NAME = "pypde"

#: The entry-point group every coral plugin registers under.
PLUGIN_GROUP = "coral.plugins"

#: The import package this distribution ships. Used to ask metadata the *reverse* question — "under
#: what name is this package registered?" — which is what catches a typo in ``PLUGIN_NAME``.
MODULE_NAME = "coral_plugin_pypde"

#: Whether *this* plugin is installed in the environment under test.
INSTALLED = bool(entry_points(group=PLUGIN_GROUP, name=PLUGIN_NAME))

#: Skip decorator for the one module collected even when the plugin is absent.
requires_this_plugin = pytest.mark.skipif(
    not INSTALLED, reason=f"plugin {PLUGIN_NAME!r} not installed"
)

#: The user-facing examples this plugin ships. There is no ``graphs/`` beside them: the other
#: plugins keep editor exports there and this one has none, so its single graph is the example.
EXAMPLES = Path(__file__).parent.parent / "examples"

#: This plugin's recorded ``node_types.json`` slice.
GOLDEN = Path(__file__).parent / "system" / "golden" / f"node_types.{PLUGIN_NAME}.json"
