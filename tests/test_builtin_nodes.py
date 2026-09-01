"""Tests for the host's own function surface — ``coral_app.builtin_nodes``.

Unit level: no graph, no executor, no registry. Each function is called directly, because what these
tests pin is the *contract* the graph layer then relies on — purity, fail-loud, determinism.

**Nothing here carries a plugin marker, deliberately.** These node types exist with zero plugins
installed; a marker would let the suite skip exactly the tests that assert that.
"""

import pytest
from coral_app.builtin_nodes import (
    BUILTIN_FUNCTIONS,
    dict_delete,
    dict_get,
    dict_new,
    dict_set,
    dict_size,
    list_append,
    list_get,
    list_new,
    list_remove_at,
    list_size,
    set_add,
    set_new,
    set_remove,
    set_size,
    set_to_list,
)


class TestListOperations:
    """The five list operations, happy path."""

    def test_list_new_is_empty(self):
        """GIVEN nothing
        WHEN list_new is called
        THEN it returns a new empty list."""
        assert list_new() == []

    def test_list_new_returns_a_fresh_list_each_time(self):
        """GIVEN two list_new nodes in one graph
        WHEN both run
        THEN they hold distinct lists, so appending to one cannot affect the other."""
        assert list_new() is not list_new()

    def test_list_append_adds_at_the_end(self):
        """GIVEN a list and an item
        WHEN list_append is called
        THEN the item is last in the returned list."""
        assert list_append([1, 2], 3) == [1, 2, 3]

    def test_list_get_returns_the_element(self):
        """GIVEN a list and a valid index
        WHEN list_get is called
        THEN it returns that element."""
        assert list_get([10, 20, 30], 1) == 20

    def test_list_get_accepts_a_negative_index(self):
        """GIVEN a negative index
        WHEN list_get is called
        THEN Python's own indexing applies and the element is counted from the end."""
        assert list_get([10, 20, 30], -1) == 30

    def test_list_size_counts_the_elements(self):
        """GIVEN a list
        WHEN list_size is called
        THEN it returns the element count."""
        assert list_size([1, 2, 3]) == 3
        assert list_size([]) == 0

    def test_list_remove_at_drops_that_element(self):
        """GIVEN a list and a valid index
        WHEN list_remove_at is called
        THEN the returned list is the original without that element."""
        assert list_remove_at([10, 20, 30], 1) == [10, 30]


class TestSetOperations:
    """The five set operations, happy path."""

    def test_set_new_is_empty(self):
        """GIVEN nothing
        WHEN set_new is called
        THEN it returns a new empty set."""
        assert set_new() == set()

    def test_set_add_inserts_the_item(self):
        """GIVEN a set and an item not in it
        WHEN set_add is called
        THEN the returned set contains it."""
        assert set_add({1, 2}, 3) == {1, 2, 3}

    def test_set_add_deduplicates(self):
        """GIVEN a set and an item already in it
        WHEN set_add is called
        THEN the set is unchanged in content — this is what makes a set a set."""
        assert set_add({1, 2}, 2) == {1, 2}

    def test_set_size_counts_the_elements(self):
        """GIVEN a set
        WHEN set_size is called
        THEN it returns the element count."""
        assert set_size({1, 2, 3}) == 3
        assert set_size(set()) == 0

    def test_set_remove_drops_the_item(self):
        """GIVEN a set containing an item
        WHEN set_remove is called
        THEN the returned set is the original without it."""
        assert set_remove({1, 2, 3}, 2) == {1, 3}

    def test_set_to_list_returns_the_elements(self):
        """GIVEN a set
        WHEN set_to_list is called
        THEN every element appears in the returned list."""
        assert set_to_list({3, 1, 2}) == [1, 2, 3]


class TestDictOperations:
    """The five dictionary operations, happy path."""

    def test_dict_new_is_empty(self):
        """GIVEN nothing
        WHEN dict_new is called
        THEN it returns a new empty dictionary."""
        assert dict_new() == {}

    def test_dict_set_adds_the_entry(self):
        """GIVEN a dictionary, a key and a value
        WHEN dict_set is called
        THEN the returned dictionary maps the key to the value."""
        assert dict_set({"a": 1}, "b", 2) == {"a": 1, "b": 2}

    def test_dict_set_replaces_an_existing_key(self):
        """GIVEN a key already present
        WHEN dict_set is called with a new value
        THEN the mapping is replaced rather than duplicated."""
        assert dict_set({"a": 1}, "a", 9) == {"a": 9}

    def test_dict_get_returns_the_value(self):
        """GIVEN a dictionary and a present key
        WHEN dict_get is called
        THEN it returns the mapped value."""
        assert dict_get({"a": 1, "b": 2}, "b") == 2

    def test_dict_size_counts_the_entries(self):
        """GIVEN a dictionary
        WHEN dict_size is called
        THEN it returns the entry count."""
        assert dict_size({"a": 1, "b": 2}) == 2
        assert dict_size({}) == 0

    def test_dict_delete_drops_the_entry(self):
        """GIVEN a dictionary and a present key
        WHEN dict_delete is called
        THEN the returned dictionary is the original without that entry."""
        assert dict_delete({"a": 1, "b": 2}, "a") == {"b": 2}


class TestPurity:
    """Every operation returns a new collection and leaves its input untouched.

    This is the property the DAG depends on: a node's result is read by every downstream consumer,
    in an order the topological sort chooses, so an in-place mutation would make the graph's outcome
    depend on that choice.
    """

    def test_list_append_does_not_mutate(self):
        """GIVEN a list fed to list_append
        WHEN the call returns
        THEN the original list is unchanged and a different object."""
        original = [1, 2]

        result = list_append(original, 3)

        assert original == [1, 2]
        assert result is not original

    def test_list_remove_at_does_not_mutate(self):
        """GIVEN a list fed to list_remove_at
        WHEN the call returns
        THEN the original list is unchanged."""
        original = [1, 2, 3]

        list_remove_at(original, 0)

        assert original == [1, 2, 3]

    def test_set_add_does_not_mutate(self):
        """GIVEN a set fed to set_add
        WHEN the call returns
        THEN the original set is unchanged and a different object."""
        original = {1, 2}

        result = set_add(original, 3)

        assert original == {1, 2}
        assert result is not original

    def test_set_remove_does_not_mutate(self):
        """GIVEN a set fed to set_remove
        WHEN the call returns
        THEN the original set is unchanged."""
        original = {1, 2, 3}

        set_remove(original, 1)

        assert original == {1, 2, 3}

    def test_dict_set_does_not_mutate(self):
        """GIVEN a dictionary fed to dict_set
        WHEN the call returns
        THEN the original dictionary is unchanged and a different object."""
        original = {"a": 1}

        result = dict_set(original, "b", 2)

        assert original == {"a": 1}
        assert result is not original

    def test_dict_delete_does_not_mutate(self):
        """GIVEN a dictionary fed to dict_delete
        WHEN the call returns
        THEN the original dictionary is unchanged."""
        original = {"a": 1, "b": 2}

        dict_delete(original, "a")

        assert original == {"a": 1, "b": 2}

    def test_a_shared_result_survives_two_consumers(self):
        """GIVEN one list consumed by two operations, as a fan-out node is
        WHEN both run against the same object
        THEN each sees the same input, so the two results do not depend on which ran first."""
        shared = [1, 2]

        first = list_append(shared, 3)
        second = list_append(shared, 4)

        assert first == [1, 2, 3]
        assert second == [1, 2, 4]
        assert shared == [1, 2]


class TestFailLoud:
    """A missing index or key raises; nothing returns a silent None."""

    def test_list_get_out_of_range_raises(self):
        """GIVEN an index past the end of the list
        WHEN list_get is called
        THEN it raises IndexError rather than returning None."""
        with pytest.raises(IndexError):
            list_get([1, 2], 5)

    def test_list_get_on_an_empty_list_raises(self):
        """GIVEN an empty list
        WHEN list_get is called at all
        THEN it raises IndexError."""
        with pytest.raises(IndexError):
            list_get([], 0)

    def test_list_remove_at_out_of_range_raises(self):
        """GIVEN an index past the end of the list
        WHEN list_remove_at is called
        THEN it raises IndexError rather than silently returning the list unchanged — which is why
        the implementation uses ``del`` and not slicing."""
        with pytest.raises(IndexError):
            list_remove_at([1, 2], 5)

    def test_set_remove_absent_item_raises(self):
        """GIVEN an item not in the set
        WHEN set_remove is called
        THEN it raises KeyError — ``remove``'s behaviour, not ``discard``'s."""
        with pytest.raises(KeyError):
            set_remove({1, 2}, 9)

    def test_dict_get_missing_key_raises(self):
        """GIVEN a key not in the dictionary
        WHEN dict_get is called
        THEN it raises KeyError rather than returning None."""
        with pytest.raises(KeyError):
            dict_get({"a": 1}, "b")

    def test_dict_delete_missing_key_raises(self):
        """GIVEN a key not in the dictionary
        WHEN dict_delete is called
        THEN it raises KeyError."""
        with pytest.raises(KeyError):
            dict_delete({"a": 1}, "b")

    def test_set_add_unhashable_item_raises(self):
        """GIVEN an unhashable item such as a list
        WHEN set_add is called
        THEN it raises TypeError rather than quietly dropping the element."""
        with pytest.raises(TypeError):
            set_add({1}, [2])

    def test_dict_set_unhashable_key_raises(self):
        """GIVEN an unhashable key
        WHEN dict_set is called
        THEN it raises TypeError."""
        with pytest.raises(TypeError):
            dict_set({}, [1], "value")


class TestSetToListDeterminism:
    """``set_to_list`` sorts, so a graph reading a set gives the same answer on every run."""

    def test_result_is_sorted(self):
        """GIVEN a set built in no particular order
        WHEN set_to_list is called
        THEN the result is sorted."""
        assert set_to_list({5, 1, 3}) == [1, 3, 5]

    def test_string_elements_are_ordered_by_value_not_by_hash(self):
        """GIVEN a set of strings, whose iteration order varies between interpreter runs
        WHEN set_to_list is called
        THEN the order is the sorted one, which is the same on every run."""
        assert set_to_list({"pear", "apple", "fig"}) == ["apple", "fig", "pear"]

    def test_repeated_calls_agree(self):
        """GIVEN one set
        WHEN set_to_list is called twice
        THEN both calls return the same order."""
        s = {"b", "a", "c"}

        assert set_to_list(s) == set_to_list(s)

    def test_incomparable_elements_raise(self):
        """GIVEN a set mixing types that cannot be compared
        WHEN set_to_list is called
        THEN it raises TypeError — the documented price of sorting, since such a set has no defined
        order for a graph to depend on."""
        with pytest.raises(TypeError):
            set_to_list({1, "a"})

    def test_empty_set_becomes_an_empty_list(self):
        """GIVEN an empty set
        WHEN set_to_list is called
        THEN it returns an empty list, not an error."""
        assert set_to_list(set()) == []


class TestBuiltinFunctionsTable:
    """The table the host merges into the function map."""

    def test_every_entry_is_keyed_by_its_own_function_name(self):
        """GIVEN the builtin table
        WHEN each key is compared with its callable's __name__
        THEN they match 1:1, so a node type never drifts from the function it runs."""
        assert all(name == func.__name__ for name, func in BUILTIN_FUNCTIONS.items())

    def test_no_name_contains_a_dot(self):
        """GIVEN the builtin node type names
        WHEN they are inspected
        THEN none contains a dot: in a node type a dot means a module or a class, and
        ``list.append`` is real Python for a method with different semantics."""
        assert all("." not in name for name in BUILTIN_FUNCTIONS)

    def test_the_table_covers_the_three_collections(self):
        """GIVEN the builtin table
        WHEN its keys are grouped by prefix
        THEN each collection contributes its five operations."""
        assert len(BUILTIN_FUNCTIONS) == 15
        for prefix in ("list_", "set_", "dict_"):
            assert len([name for name in BUILTIN_FUNCTIONS if name.startswith(prefix)]) == 5

    def test_every_entry_is_callable(self):
        """GIVEN the builtin table
        WHEN each value is inspected
        THEN it is callable, so the executor can resolve any of them."""
        assert all(callable(func) for func in BUILTIN_FUNCTIONS.values())
