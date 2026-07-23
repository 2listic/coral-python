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
