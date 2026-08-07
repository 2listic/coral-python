"""The `Plugin` ABC — the whole of `coral-core`, and the contract every plugin subclasses.

The contract must be *enforced*, not duck-typed: a subclass that omits either abstract method
cannot be instantiated. That is all this package promises, so it is all these tests assert.

Each plugin asserts its *own* conformance in its own `tests/unit/` — a plugin's conformance is a
fact about that plugin, not about the ABC.
"""

import pytest
from coral_core import Plugin


class TestPluginContract:
    """The Plugin ABC enforces get_functions() / get_classes()."""

    def test_plugin_cannot_be_instantiated(self):
        """GIVEN the abstract Plugin base
        WHEN it is instantiated directly
        THEN a TypeError is raised (abstract methods unimplemented)."""
        with pytest.raises(TypeError):
            Plugin()

    def test_subclass_missing_get_classes_cannot_be_instantiated(self):
        """GIVEN a subclass that implements only get_functions()
        WHEN it is instantiated
        THEN a TypeError is raised (get_classes still abstract)."""

        class Partial(Plugin):
            def get_functions(self):
                return {}

        with pytest.raises(TypeError):
            Partial()

    def test_subclass_missing_get_functions_cannot_be_instantiated(self):
        """GIVEN a subclass that implements only get_classes()
        WHEN it is instantiated
        THEN a TypeError is raised (get_functions still abstract)."""

        class Partial(Plugin):
            def get_classes(self):
                return {}

        with pytest.raises(TypeError):
            Partial()

    def test_complete_subclass_can_be_instantiated(self):
        """GIVEN a subclass implementing both abstract methods
        WHEN it is instantiated and its methods called
        THEN it constructs and returns the declared maps."""

        class Complete(Plugin):
            def get_functions(self):
                return {"f": lambda: None}

            def get_classes(self):
                return {"C": int}

        plugin = Complete()
        assert plugin.get_functions().keys() == {"f"}
        assert plugin.get_classes() == {"C": int}
