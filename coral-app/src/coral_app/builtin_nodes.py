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

from typing import Any, Callable, Dict

__all__ = [
    "BUILTIN_FUNCTIONS",
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


# ── list ──


def list_new() -> list:
    """Create an empty list."""
    return []


def list_append(lst: list, item: Any) -> list:
    """Return a new list with ``item`` added at the end."""
    return [*lst, item]


def list_get(lst: list, index: int) -> Any:
    """Return the element at ``index``, raising ``IndexError`` if there is none."""
    return lst[index]


def list_size(lst: list) -> int:
    """Return the number of elements in the list."""
    return len(lst)


def list_remove_at(lst: list, index: int) -> list:
    """Return a new list without the element at ``index``.

    Copy then ``del``: slicing around the index would silently no-op on an out-of-range index,
    whereas ``del`` raises ``IndexError`` — the removal has to fail loud like the lookup does.
    """
    out = list(lst)
    del out[index]
    return out


# ── set ──


def set_new() -> set:
    """Create an empty set."""
    return set()


def set_add(s: set, item: Any) -> set:
    """Return a new set containing ``item`` as well.

    Raises ``TypeError`` if ``item`` is unhashable — a set cannot hold it, and silently dropping it
    would leave the graph with a set that quietly lost an element.
    """
    return s | {item}


def set_to_list(s: set) -> list:
    """Return the set's elements as a **sorted** list.

    Sorted, not merely iterated: a set of strings iterates in a different order *between runs*
    (hash randomisation), which would make a graph's output non-reproducible for no reason the
    author could see. The price is that a set of mutually incomparable elements (``{1, "a"}``)
    raises ``TypeError`` here rather than at the consumer — accepted, because a graph that depends
    on the iteration order of such a set has no defined answer anyway.
    """
    return sorted(s)


def set_size(s: set) -> int:
    """Return the number of elements in the set."""
    return len(s)


def set_remove(s: set, item: Any) -> set:
    """Return a new set without ``item``, raising ``KeyError`` if it is not there.

    ``remove``, not ``discard``: removing something absent is a wiring mistake worth reporting.
    """
    out = set(s)
    out.remove(item)
    return out


# ── dict ──


def dict_new() -> dict:
    """Create an empty dictionary."""
    return {}


def dict_set(d: dict, key: Any, value: Any) -> dict:
    """Return a new dictionary with ``key`` mapped to ``value``, replacing any previous mapping."""
    return {**d, key: value}


def dict_get(d: dict, key: Any) -> Any:
    """Return the value ``key`` maps to, raising ``KeyError`` if it is absent."""
    return d[key]


def dict_size(d: dict) -> int:
    """Return the number of entries in the dictionary."""
    return len(d)


def dict_delete(d: dict, key: Any) -> dict:
    """Return a new dictionary without ``key``, raising ``KeyError`` if it is absent."""
    out = dict(d)
    del out[key]
    return out


#: Node type -> callable, for every function the host itself provides. Merged into the function map
#: after the plugins, so a plugin cannot shadow one of these names.
BUILTIN_FUNCTIONS: Dict[str, Callable] = {
    "list_new": list_new,
    "list_append": list_append,
    "list_get": list_get,
    "list_size": list_size,
    "list_remove_at": list_remove_at,
    "set_new": set_new,
    "set_add": set_add,
    "set_to_list": set_to_list,
    "set_size": set_size,
    "set_remove": set_remove,
    "dict_new": dict_new,
    "dict_set": dict_set,
    "dict_get": dict_get,
    "dict_size": dict_size,
    "dict_delete": dict_delete,
}
