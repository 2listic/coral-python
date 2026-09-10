"""Stage 5 — ``coral_app.registry``: rendering the port table into ``node_types.json``.

This file owns the **format**, which is one half of the contract with the DealiiX platform: what keys
an entry has, how ports are numbered, when ``outputs`` is ``[-1]``, which string a socket type gets.
All of that is the host's, so all of it is asserted against the designed specimen — never against a
plugin's surface.

What a *particular* plugin renders to is that plugin's own golden, in its own suite. The two are
deliberately separate: renaming a format key must not require editing three plugin packages before
anyone can see what changed.
"""

import json
from pathlib import Path
from typing import Any, List

import pytest
from coral_app import BUILTIN_FUNCTIONS, PRIMITIVES_MAP, build_class_map, build_function_map
from coral_app.registry import generate_registry, python_type_to_string, save_registry_to_file
from specimen import RIVAL, SPECIMEN

GOLDEN = Path(__file__).parent / "golden" / "node_types.format.json"


def outputs_of(entry: dict) -> List[dict]:
    """The output arguments of a registry entry, in order."""
    return [arg for arg in entry["arguments"] if arg["connection_type"] == "output"]


def inputs_of(entry: dict) -> List[dict]:
    """The input arguments of a registry entry, in order."""
    return [arg for arg in entry["arguments"] if arg["connection_type"] == "input"]


@pytest.fixture
def registry(specimen_plugins):
    """The registry for the specimen plugin — one entry per node type it and the host contribute."""
    return generate_registry(
        build_function_map(include=[SPECIMEN]),
        list(PRIMITIVES_MAP),
        build_class_map(include=[SPECIMEN]),
    )


class TestPythonTypeToString:
    """The socket type strings, which are what the editor matches on."""

    @pytest.mark.parametrize(
        "py_type, name",
        [(int, "int"), (float, "float"), (str, "str"), (bool, "bool"), (type(None), "none")],
    )
    def test_primitive_types(self, py_type, name):
        """GIVEN a primitive Python type
        WHEN it is rendered
        THEN it becomes the protocol's name for it."""
        assert python_type_to_string(py_type) == name

    @pytest.mark.parametrize("py_type, name", [(list, "list"), (set, "set"), (dict, "dict")])
    def test_collection_types(self, py_type, name):
        """GIVEN a bare collection type, which is a socket type but not a node type
        WHEN it is rendered
        THEN it gets its own name rather than collapsing to 'any'."""
        assert python_type_to_string(py_type) == name

    def test_parameterised_generic_is_any(self):
        """GIVEN a parameterised generic such as List[int]
        WHEN it is rendered
        THEN it is 'any': only the bare `list` is a name the format knows, and the graph's edge check
        cannot judge a generic alias either, so claiming 'list' here would promise more than is
        verified."""
        from typing import List as ListAlias

        assert python_type_to_string(ListAlias[int]) == "any"

    def test_any_and_a_missing_annotation_are_both_any(self):
        """GIVEN `Any` and a missing annotation
        WHEN each is rendered
        THEN both are 'any' — the port table already normalised them to the same thing."""
        import inspect

        assert python_type_to_string(Any) == "any"
        assert python_type_to_string(inspect.Signature.empty) == "any"

    def test_an_unknown_class_is_any(self):
        """GIVEN a class the format has no name for
        WHEN it is rendered
        THEN it is 'any' — an instance socket carries no class name in this format."""

        class Custom:
            pass

        assert python_type_to_string(Custom) == "any"


class TestEveryEntryIsWellFormed:
    """The keys the platform's registry validator requires, on every entry."""

    def test_entries_are_keyed_by_their_own_type(self, registry):
        """GIVEN a generated registry
        WHEN each entry is read
        THEN its `type` equals its key: the editor looks entries up as registry[type]."""
        for key, entry in registry.items():
            assert entry["type"] == key

    def test_every_entry_has_the_required_keys(self, registry):
        """GIVEN a generated registry
        WHEN each entry is read
        THEN it carries node_type, arguments, inputs and outputs.

        The platform *skips* an entry missing any of them, so even a primitive — which takes no
        input — must carry an empty `arguments` list."""
        for key, entry in registry.items():
            for required in ("node_type", "arguments", "inputs", "outputs"):
                assert required in entry, f"{key} missing {required}"

    def test_the_four_kinds_all_appear(self, registry):
        """GIVEN the specimen, which contributes all four kinds
        WHEN the registry is generated
        THEN each kind is present under the node type that produced it."""
        assert registry["int"]["node_type"] == "primitive"
        assert registry["add_pair"]["node_type"] == "function"
        assert registry["Accumulator"]["node_type"] == "constructor"
        assert registry["Accumulator.add"]["node_type"] == "method"

    def test_input_indices_number_the_input_arguments(self, registry):
        """GIVEN any entry
        WHEN its `inputs` list is compared with its input arguments
        THEN the indices are 0..n-1, one per input argument."""
        for key, entry in registry.items():
            assert entry["inputs"] == list(range(len(inputs_of(entry)))), key


class TestFunctionEntries:
    """Function nodes, including the two shapes no plugin had before the builtins."""

    def test_a_plain_function_numbers_its_ports(self, registry):
        """GIVEN a two-parameter function returning one value
        WHEN its entry is read
        THEN its inputs are 0 and 1, and its single output continues the numbering at 2."""
        entry = registry["add_pair"]

        assert entry["inputs"] == [0, 1]
        assert entry["outputs"] == [2]
        assert inputs_of(entry) == [
            {"connection_type": "input", "type": "float", "name": "a"},
            {"connection_type": "input", "type": "float", "name": "b"},
        ]
        assert outputs_of(entry) == [{"connection_type": "output", "type": "float", "name": ""}]

    def test_a_zero_input_function(self, registry):
        """GIVEN a function taking nothing
        WHEN its entry is read
        THEN `inputs` is empty and its output is port 0.

        New for the platform when the builtins arrived: a primitive also takes no input, but uses
        `outputs: [-1]`."""
        entry = registry["make_one"]

        assert entry["inputs"] == []
        assert entry["outputs"] == [0]
        assert entry["node_type"] == "function"

    def test_a_none_returning_function_has_no_outputs(self, registry):
        """GIVEN a function annotated `-> None`
        WHEN its entry is read
        THEN it declares no output at all — there is nothing for an edge to carry."""
        entry = registry["record"]

        assert entry["outputs"] == []
        assert outputs_of(entry) == []

    def test_a_multi_output_function_numbers_each_element(self, registry):
        """GIVEN a function annotated `Tuple[float, str, bool]`
        WHEN its entry is read
        THEN it has three outputs, numbered after its inputs, each carrying its own type."""
        entry = registry["split_triple"]

        assert entry["inputs"] == [0]
        assert entry["outputs"] == [1, 2, 3]
        assert [arg["type"] for arg in outputs_of(entry)] == ["float", "str", "bool"]

    def test_a_missing_annotation_renders_as_any(self, registry):
        """GIVEN a function with no annotations at all
        WHEN its entry is read
        THEN its input socket is 'any' and it declares no output."""
        entry = registry["unannotated"]

        assert inputs_of(entry) == [{"connection_type": "input", "type": "any", "name": "value"}]
        assert entry["outputs"] == []

    def test_an_explicit_any_renders_as_any(self, registry):
        """GIVEN a function annotated `Any` in and out
        WHEN its entry is read
        THEN both sockets are 'any' — indistinguishable from the unannotated case, by design."""
        entry = registry["anything"]

        assert inputs_of(entry)[0]["type"] == "any"
        assert outputs_of(entry)[0]["type"] == "any"

    def test_a_dotted_function_name_is_a_function_entry(self, registry):
        """GIVEN a function registered under a dotted name
        WHEN its entry is read
        THEN it is a function node keyed by that name, not a method of some class."""
        entry = registry["specimen.ratio"]

        assert entry["node_type"] == "function"
        assert entry["type"] == "specimen.ratio"


class TestConstructorAndMethodEntries:
    """Classes contribute a constructor plus one entry per public method."""

    def test_a_constructor_omits_self_and_outputs_minus_one(self, registry):
        """GIVEN a class
        WHEN its constructor entry is read
        THEN its inputs are the __init__ parameters without self, and `outputs` is [-1].

        `[-1]` with no output argument is the format's convention for "one unnamed output"."""
        entry = registry["Accumulator"]

        assert inputs_of(entry) == [{"connection_type": "input", "type": "float", "name": "start"}]
        assert entry["outputs"] == [-1]
        assert outputs_of(entry) == []

    def test_a_method_takes_the_instance_at_port_zero(self, registry):
        """GIVEN a method with one parameter
        WHEN its entry is read
        THEN port 0 is the instance and the parameter follows.

        The instance socket renders as 'any': the format has no name for a class, which is why an
        instance edge is checked by the *graph* against annotations rather than by the editor."""
        entry = registry["Accumulator.add"]

        assert inputs_of(entry) == [
            {"connection_type": "input", "type": "any", "name": "self"},
            {"connection_type": "input", "type": "float", "name": "amount"},
        ]
        assert entry["outputs"] == [2]

    def test_a_method_taking_only_self_has_one_input(self, registry):
        """GIVEN a method whose only parameter is self
        WHEN its entry is read
        THEN it has exactly one input port."""
        assert registry["Accumulator.total"]["inputs"] == [0]

    def test_private_members_and_attributes_are_not_node_types(self, registry):
        """GIVEN a class with an underscore method and a plain class attribute
        WHEN the registry is generated
        THEN neither becomes an entry."""
        assert "Accumulator._hidden" not in registry
        assert "Accumulator.class_attribute" not in registry

    def test_a_subclass_registers_its_inherited_methods_too(self, registry):
        """GIVEN a subclass
        WHEN the registry is generated
        THEN it carries its own constructor and every public method it has, inherited ones included —
             each keyed under the subclass, because the editor offers node types, not hierarchies."""
        assert registry["PreciseAccumulator"]["node_type"] == "constructor"
        assert registry["PreciseAccumulator.rounded"]["node_type"] == "method"
        assert registry["PreciseAccumulator.add"]["node_type"] == "method"


class TestPrimitiveEntries:
    """Primitives are always present, and are the one kind carrying a `value`."""

    def test_a_primitive_entry(self, registry):
        """GIVEN a primitive type
        WHEN its entry is read
        THEN it has an empty `arguments`, a `value`, no inputs, and `outputs: [-1]`."""
        entry = registry["int"]

        assert entry == {
            "arguments": [],
            "value": "",
            "inputs": [],
            "outputs": [-1],
            "node_type": "primitive",
            "type": "int",
        }

    def test_every_primitive_is_present(self, registry):
        """GIVEN any plugin selection
        WHEN the registry is generated
        THEN every primitive type name has an entry: they are the host's, not a plugin's."""
        assert set(PRIMITIVES_MAP) <= set(registry)


class TestBuiltinCollectionEntries:
    """The host's own collection nodes, as the platform sees them.

    Generated with `include=[]`, which is also the contract being asserted: they are there with
    nothing installed.
    """

    @pytest.fixture
    def host_registry(self):
        """The registry the host emits on its own."""
        return generate_registry(build_function_map(include=[]), list(PRIMITIVES_MAP))

    def test_a_collection_socket_is_typed_not_any(self, host_registry):
        """GIVEN list_append, whose first parameter is annotated `list`
        WHEN the registry renders it
        THEN the socket's type is 'list' — the payoff of naming the collection types."""
        assert host_registry["list_append"]["arguments"][0] == {
            "connection_type": "input",
            "type": "list",
            "name": "lst",
        }

    def test_each_creator_returns_its_own_collection_type(self, host_registry):
        """GIVEN the three creators, one per collection
        WHEN their output sockets are read
        THEN each names its own collection type."""
        for node_type, type_name in (
            ("list_new", "list"),
            ("set_new", "set"),
            ("dict_new", "dict"),
        ):
            assert [arg["type"] for arg in outputs_of(host_registry[node_type])] == [type_name]

    def test_a_creator_has_no_inputs_and_one_output(self, host_registry):
        """GIVEN list_new, which takes nothing
        WHEN its entry is read
        THEN it declares zero inputs and a single output port."""
        assert host_registry["list_new"]["inputs"] == []
        assert host_registry["list_new"]["outputs"] == [0]
        assert host_registry["list_new"]["node_type"] == "function"

    def test_element_ports_stay_any(self, host_registry):
        """GIVEN list_append's item parameter, annotated Any by design
        WHEN the registry renders it
        THEN it is 'any': collections carry no element typing, so anything may be appended."""
        assert host_registry["list_append"]["arguments"][1] == {
            "connection_type": "input",
            "type": "any",
            "name": "item",
        }

    def test_extractors_return_any(self, host_registry):
        """GIVEN list_get and dict_get, which return an element
        WHEN their output socket is read
        THEN it is 'any' — the element type is unknown, which is what makes them wire anywhere."""
        for node_type in ("list_get", "dict_get"):
            assert [arg["type"] for arg in outputs_of(host_registry[node_type])] == ["any"]

    def test_size_returns_int(self, host_registry):
        """GIVEN the three inspect operations
        WHEN their output socket is read
        THEN it is 'int', so a size can feed a numeric port."""
        for node_type in ("list_size", "set_size", "dict_size"):
            assert [arg["type"] for arg in outputs_of(host_registry[node_type])] == ["int"]

    def test_set_to_list_crosses_collection_types(self, host_registry):
        """GIVEN set_to_list, the bridge from a set to an indexable list
        WHEN its entry is read
        THEN it takes a 'set' and returns a 'list', both typed."""
        arguments = host_registry["set_to_list"]["arguments"]

        assert arguments[0]["type"] == "set"
        assert arguments[1] == {"connection_type": "output", "type": "list", "name": ""}


class TestSelection:
    """Which node types a selection yields."""

    def test_only_the_selected_plugin_contributes(self, specimen_plugins):
        """GIVEN one plugin selected
        WHEN the registry is generated
        THEN the other plugin's nodes are absent, and the host's own are still present."""
        registry = generate_registry(
            build_function_map(include=[SPECIMEN]),
            list(PRIMITIVES_MAP),
            build_class_map(include=[SPECIMEN]),
        )

        assert "add_pair" in registry
        assert "rival_only" not in registry
        assert "list_new" in registry and "int" in registry

    def test_exclude_removes_a_plugin_after_include(self, specimen_plugins):
        """GIVEN two plugins included and one of them excluded
        WHEN the registry is generated
        THEN the excluded plugin's nodes are gone."""
        registry = generate_registry(
            build_function_map(include=[SPECIMEN, RIVAL], exclude=[RIVAL]),
            list(PRIMITIVES_MAP),
            build_class_map(include=[SPECIMEN, RIVAL], exclude=[RIVAL]),
        )

        assert "add_pair" in registry
        assert "rival_only" not in registry and "Tally" not in registry

    def test_primitives_are_not_excludable(self, specimen_plugins):
        """GIVEN no plugin at all
        WHEN the registry is generated
        THEN the primitives are still there: no selection can remove them."""
        registry = generate_registry(build_function_map(include=[]), list(PRIMITIVES_MAP))

        assert set(PRIMITIVES_MAP) <= set(registry)


class TestKeyOrder:
    """Key order is part of the file, so it is pinned: plugins in selection order, builtins last."""

    def test_plugins_come_in_selection_order_and_builtins_last(self, specimen_plugins):
        """GIVEN two plugins selected in a given order
        WHEN the registry is generated
        THEN primitives come first, then each plugin's functions in selection order, then the host's
             builtins — so adding a builtin never moves a plugin's entry."""
        keys = list(
            generate_registry(
                build_function_map(include=[SPECIMEN, RIVAL]),
                list(PRIMITIVES_MAP),
                build_class_map(include=[SPECIMEN, RIVAL]),
            )
        )

        assert keys[: len(PRIMITIVES_MAP)] == list(PRIMITIVES_MAP)
        assert keys.index("add_pair") < keys.index("rival_only")
        assert keys.index("rival_only") < keys.index("list_new")
        # Constructors and methods follow the functions, so the builtins are not last overall.
        assert keys.index("list_new") < keys.index("Accumulator")

    def test_reversing_the_selection_reverses_the_plugin_blocks(self, specimen_plugins):
        """GIVEN the same two plugins in the opposite order
        WHEN the registry is generated
        THEN their blocks swap — the order is the caller's, not alphabetical."""
        keys = list(
            generate_registry(
                build_function_map(include=[RIVAL, SPECIMEN]),
                list(PRIMITIVES_MAP),
                build_class_map(include=[RIVAL, SPECIMEN]),
            )
        )

        assert keys.index("rival_only") < keys.index("add_pair")
        assert keys.index("Tally") < keys.index("Accumulator")


class TestSaveRegistryToFile:
    """Writing the file — the only part of the pipeline the CLI's `register` adds."""

    def test_it_writes_what_generate_returns(self, tmp_path, specimen_plugins):
        """GIVEN a plugin selection
        WHEN the registry is saved and read back
        THEN the file's content equals what generate_registry produces for that selection."""
        out = tmp_path / "node_types.json"

        returned = save_registry_to_file(str(out), plugins=[SPECIMEN])

        expected = generate_registry(
            build_function_map(include=[SPECIMEN]),
            list(PRIMITIVES_MAP),
            build_class_map(include=[SPECIMEN]),
        )
        assert json.loads(out.read_text()) == expected
        assert returned == expected

    def test_the_default_filename_lands_in_the_current_directory(self, tmp_path, specimen_plugins):
        """GIVEN no filename
        WHEN the registry is saved
        THEN it is written to `registry-py.json` in the current directory.

        The launcher relies on cwd: `coral register` must write where the caller stands."""
        save_registry_to_file(plugins=[SPECIMEN])

        assert (tmp_path / "registry-py.json").exists()


class TestFormatGolden:
    """The format, byte-for-byte.

    One half of the C0 contract with the DealiiX platform. The golden is generated from the specimen
    plugins, so it pins the *format* and the *ordering* without depending on any plugin's surface —
    a plugin adding a function cannot move these bytes, and a format change shows up as a diff here
    rather than in three plugin packages at once.

    Regenerate deliberately, never to make a failure go away::

        uv run python -c "..."   # see the command in the test below
    """

    def test_the_registry_for_the_specimen_plugins_matches_the_golden(
        self, tmp_path, specimen_plugins
    ):
        """GIVEN the recorded golden for the two specimen plugins
        WHEN save_registry_to_file regenerates it
        THEN the emitted file is byte-for-byte identical."""
        assert GOLDEN.exists(), f"missing golden: {GOLDEN}"

        out = tmp_path / GOLDEN.name
        save_registry_to_file(str(out), plugins=[SPECIMEN, RIVAL])

        assert out.read_bytes() == GOLDEN.read_bytes(), (
            f"registry format diverged from {GOLDEN.name}; regenerate it only on purpose"
        )

    def test_the_golden_covers_all_four_kinds_and_the_builtins(self):
        """GIVEN the golden file
        WHEN it is parsed
        THEN it holds every node kind plus the host's builtins — otherwise it would pin a format it
             does not actually exercise."""
        entries = json.loads(GOLDEN.read_text())

        kinds = {entry["node_type"] for entry in entries.values()}
        assert kinds == {"primitive", "function", "constructor", "method"}
        assert set(BUILTIN_FUNCTIONS) <= set(entries)
