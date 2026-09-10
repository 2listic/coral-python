"""Is this plugin installed, and under the name the platform expects?

The only module in this suite collected when the plugin is absent — it imports nothing from the
plugin, so it survives to report a visible skip instead of the whole directory quietly vanishing (see
``conftest.py``).
"""

from importlib.metadata import entry_points

import pytest
from math_suite import MODULE_NAME, PLUGIN_GROUP, PLUGIN_NAME, requires_this_plugin


@requires_this_plugin
def test_the_entry_point_name_is_the_one_the_platform_uses():
    """GIVEN this plugin installed
    WHEN the ``coral.plugins`` entry points are read
    THEN one is registered under exactly this plugin's name.

    The name is the whole of the plugin's identity: it is what ``-p math`` selects, what the DealiiX
    platform's ``coralPluginPath`` lists, and what ``discover()`` returns. Renaming it is a breaking
    change for the platform, so it is asserted against a hand-written constant — a check derived from
    metadata would happily follow the rename and assert nothing.
    """
    assert entry_points(group=PLUGIN_GROUP, name=PLUGIN_NAME)


@requires_this_plugin
def test_the_entry_point_resolves_to_this_plugin_class():
    """GIVEN this plugin's entry point
    WHEN it is loaded
    THEN it resolves to a class in this plugin's own module — the host instantiates the *class*."""
    from coral_plugin_math import MathPlugin

    (found,) = entry_points(group=PLUGIN_GROUP, name=PLUGIN_NAME)

    assert found.load() is MathPlugin


def test_this_distribution_is_registered_under_its_declared_name():
    """GIVEN whatever plugins are installed
    WHEN the ones pointing into this package's module are collected
    THEN the only name among them is ``PLUGIN_NAME``.

    This is the test that makes the self-guard trustworthy. A typo in ``PLUGIN_NAME`` would leave
    every other test here *skipped* — green, and covering nothing. Asking the question the other way
    round ("under what name is this package registered?") fails loudly instead. It reads metadata
    only, so it never imports the plugin and can run even when the distribution is absent.
    """
    mine = {
        ep.name for ep in entry_points(group=PLUGIN_GROUP) if ep.module.split(".")[0] == MODULE_NAME
    }

    if not mine:
        pytest.skip(f"{MODULE_NAME} is not installed")

    assert mine == {PLUGIN_NAME}, (
        f"{MODULE_NAME} is registered as {sorted(mine)}, but this suite expects {PLUGIN_NAME!r}"
    )
