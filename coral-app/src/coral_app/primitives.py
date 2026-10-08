from typing import Any

# Map primitive type names to Python types.
#
# A primitive is a node carrying a literal in its `value` field; its type says how to read it. A
# scalar (`int`, `float`, `str`, `bool`) is cast by its type, `any` passes the value through
# unchanged and `none` is `None`. A collection (`list`, `set`, `dict`) is written as a JSON string
# (`"[1, 2]"`, `"{\"a\": 1}"`) which the executor parses: the editor can only produce strings, and
# the reference backend reads its collection literals the same way.
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
    "list": list,
    "set": set,
    "dict": dict,
}
