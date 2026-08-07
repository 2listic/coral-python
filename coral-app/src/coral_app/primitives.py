from typing import Any

# Map primitive type names to Python types.
#
# PRIMITIVES_MAP lives in the host, not in coral-core: no plugin references it, and the registry /
# executor (both host-side) are its only consumers.
PRIMITIVES_MAP = {
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "any": Any,
    "none": type(None),
}

# The collection types, which are type names *only* — deliberately not node types.
#
# A primitive is a node: it carries a literal in its `value` field, which the declared type casts.
# A collection cannot be that, because JSON cannot express a literal set or dict, so such a node
# could only ever produce an empty collection — exactly what `list_new()` / `set_new()` / `dict_new()`
# in `builtin_nodes.py` already return. Two node types for one behaviour is worse than one, so the
# collections live here for their *names* alone: `registry.py` needs them to render a `list`
# annotation as `"list"` instead of `"any"`, and nothing else consumes them. A graph naming
# `{"type": "list"}` is therefore an unknown node type, which the graph's own validation rejects —
# there is one way to build a collection, and it is the function.
COLLECTION_TYPES = {
    "list": list,
    "set": set,
    "dict": dict,
}

# Every type name the registry can render on a socket: the primitive node types plus the
# collections. Derived, never edited directly — the two maps above are the source of truth.
TYPE_NAMES = {**PRIMITIVES_MAP, **COLLECTION_TYPES}
