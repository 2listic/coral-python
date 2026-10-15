"""The host's own function surface: operations on lists, sets and dictionaries.

These are node types available under **any** ``-p`` selection, and even with no plugin installed at
all — exactly like the primitives in :mod:`coral_app.primitives`. The host guarantees them, so a
graph using them runs anywhere a coral host runs. This module is to callables what ``primitives.py``
is to types, and like that module it imports nothing from ``coral_app``.

Three properties hold for every operation here, and graphs depend on all three:

**Pure.** Every operation returns a *new* collection and never touches its input. A node's result is
shared by every downstream consumer, so an in-place mutation would make the graph's outcome depend on
the order the consumers happen to run in — which the topological sort is free to choose.

**Fail loud.** A missing index or key raises (``IndexError`` / ``KeyError``). There is no ``None``
fallback and no default argument: graph validation requires every input port to be wired, so a
default would be unreachable anyway.

**No element typing.** Annotations are the bare ``list`` / ``set`` / ``dict``, and elements are
``Any``. A parameterised generic such as ``List[int]`` would render as ``"any"`` in the registry and
make the graph's edge type check skip the edge entirely, so it would buy nothing and cost the socket
its type.

Names are underscored (``list_append``, not ``list.append``). In a node type a dot already means a
module (``math.sqrt``) or a class (``Calculator.add_to_value``) — and ``list.append`` is real Python
for a builtin method with *different* semantics: it mutates and returns ``None``. The name would
assert something false.
"""

from typing import Any

from coral_core import Plugin

__all__ = [
    "BUILTINS",
    "list_new",
    "list_append",
    "list_get",
    "list_size",
    "list_remove_at",
    "set_new",
    "set_add",
    "set_to_list",
    "set_size",
    "set_remove",
    "dict_new",
    "dict_set",
    "dict_get",
    "dict_size",
    "dict_delete",
]

#: The host's own node types, declared the way a plugin declares its own. Not discovered by entry
#: point: merged into the function map after the plugins, so a plugin cannot shadow one of them.
BUILTINS = Plugin()


# ── list ──


@BUILTINS.function
def list_new() -> list:
    """Create an empty list."""
    return []


@BUILTINS.function
def list_append(lst: list, item: Any) -> list:
    """Return a new list with ``item`` added at the end."""
    return [*lst, item]


@BUILTINS.function
def list_get(lst: list, index: int) -> Any:
    """Return the element at ``index``, raising ``IndexError`` if there is none."""
    return lst[index]


@BUILTINS.function
def list_size(lst: list) -> int:
    """Return the number of elements in the list."""
    return len(lst)


@BUILTINS.function
def list_remove_at(lst: list, index: int) -> list:
    """Return a new list without the element at ``index``.

    Copy then ``del``: slicing around the index would silently no-op on an out-of-range index,
    whereas ``del`` raises ``IndexError`` — the removal has to fail loud like the lookup does.
    """
    out = list(lst)
    del out[index]
    return out


# ── set ──


@BUILTINS.function
def set_new() -> set:
    """Create an empty set."""
    return set()


@BUILTINS.function
def set_add(s: set, item: Any) -> set:
    """Return a new set containing ``item`` as well.

    Raises ``TypeError`` if ``item`` is unhashable — a set cannot hold it, and silently dropping it
    would leave the graph with a set that quietly lost an element.
    """
    return s | {item}


@BUILTINS.function
def set_to_list(s: set) -> list:
    """Return the set's elements as a **sorted** list.

    Sorted, not merely iterated: a set of strings iterates in a different order *between runs*
    (hash randomisation), which would make a graph's output non-reproducible for no reason the
    author could see. The price is that a set of mutually incomparable elements (``{1, "a"}``)
    raises ``TypeError`` here rather than at the consumer — accepted, because a graph that depends
    on the iteration order of such a set has no defined answer anyway.
    """
    return sorted(s)


@BUILTINS.function
def set_size(s: set) -> int:
    """Return the number of elements in the set."""
    return len(s)


@BUILTINS.function
def set_remove(s: set, item: Any) -> set:
    """Return a new set without ``item``, raising ``KeyError`` if it is not there.

    ``remove``, not ``discard``: removing something absent is a wiring mistake worth reporting.
    """
    out = set(s)
    out.remove(item)
    return out


# ── dict ──


@BUILTINS.function
def dict_new() -> dict:
    """Create an empty dictionary."""
    return {}


@BUILTINS.function
def dict_set(d: dict, key: Any, value: Any) -> dict:
    """Return a new dictionary with ``key`` mapped to ``value``, replacing any previous mapping."""
    return {**d, key: value}


@BUILTINS.function
def dict_get(d: dict, key: Any) -> Any:
    """Return the value ``key`` maps to, raising ``KeyError`` if it is absent."""
    return d[key]


@BUILTINS.function
def dict_size(d: dict) -> int:
    """Return the number of entries in the dictionary."""
    return len(d)


@BUILTINS.function
def dict_delete(d: dict, key: Any) -> dict:
    """Return a new dictionary without ``key``, raising ``KeyError`` if it is absent."""
    out = dict(d)
    del out[key]
    return out
