import json
from typing import Any

# Map primitive type names to Python types.
#
# A primitive is a node carrying a literal in its `value` field; its type says how to read it. A
# scalar (`int`, `float`, `str`) is cast by its type, a `bool` is `true` or `false`, `any` passes
# the value through unchanged and `none` is `None`. A collection (`list`, `set`, `dict`) is written
# as a JSON string (`"[1, 2]"`, `"{\"a\": 1}"`) which `read_literal` below parses: the editor can
# only produce strings, and the reference backend reads its collection literals the same way.
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

# The JSON value each collection literal must parse to: a set is written as an array.
_JSON_SHAPE = {"list": list, "set": list, "dict": dict}

# A primitive entry's registry `value`: the editor copies it into a node the user drops. A
# collection's is its empty literal and a bool's is `false`, both of which `read_literal` accepts;
# any other primitive has none, and the registry writes `""`.
DEFAULT_LITERAL = {
    "bool": "false",
    **{node_type: json.dumps(shape()) for node_type, shape in _JSON_SHAPE.items()},
}

# A parsed JSON value's type -> the name JSON gives it, for the error messages.
_JSON_NAME = {
    list: "array",
    dict: "object",
    str: "string",
    bool: "boolean",
    int: "number",
    float: "number",
    type(None): "null",
}


def read_literal(node_type: str, value: Any, label: str) -> Any:
    """A primitive node's ``value``, read the way its declared type says.

    A scalar is cast by its type: the protocol may carry it as a string (``"42"``) or natively
    (``42``), and the cast accepts both. ``any`` passes the value through as the JSON carried it,
    and ``none`` is ``None`` whatever ``value`` holds. A value the cast refuses (``int("")``)
    raises ``ValueError`` naming the node, chained to the cast's own error.

    A ``bool`` is the exception to the cast, because ``bool("false")`` is ``True``: it accepts
    ``true`` and ``false``, natively or as the strings ``"true"`` and ``"false"``, and nothing else.

    A collection must be a JSON string, which is parsed: ``'[1, 2]'`` for a ``list`` or a ``set``,
    ``'{"a": 1}'`` for a ``dict``. A native array or object is refused, so a literal has one
    spelling, the one the editor writes. Errors raised by the parsing itself — malformed JSON
    (``json.JSONDecodeError``) or an unhashable set element (``TypeError``) — are raised again as
    ``ValueError`` naming the node, chained to the parser's own error.

    Args:
        node_type: The node's ``type``, a key of ``PRIMITIVES_MAP``.
        value: The node's ``value`` field.
        label: How an error names the node, e.g. ``"'0' ('ids')"``.

    Raises:
        ValueError: if a scalar's cast refuses its ``value``, if a ``bool``'s ``value`` is neither
            ``true`` nor ``false``, or if a collection's ``value`` is not a string, is not valid
            JSON, parses to the wrong JSON shape, or holds an unhashable element in a ``set``.
    """
    converter = PRIMITIVES_MAP[node_type]
    node = f"Node {label} of type {node_type!r}"

    if converter is type(None):
        return None
    if converter is Any:  # Don't convert value if type is Any
        return value
    if converter is bool:
        if isinstance(value, bool):
            return value
        if value == "true":
            return True
        if value == "false":
            return False
        raise ValueError(f"{node} needs true or false, got {value!r}")
    if node_type not in _JSON_SHAPE:
        try:
            return converter(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{node} cannot read {value!r}: {exc}") from exc

    if not isinstance(value, str):
        got = _JSON_NAME.get(type(value), type(value).__name__)
        raise ValueError(f"{node} needs a JSON string, got {got}")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{node} cannot read {value!r}: {exc}") from exc
    shape = _JSON_SHAPE[node_type]
    if type(parsed) is not shape:
        raise ValueError(f"{node} needs a JSON {_JSON_NAME[shape]}, got {_JSON_NAME[type(parsed)]}")
    try:
        return converter(parsed)
    except TypeError as exc:
        raise ValueError(f"{node} cannot read {value!r}: {exc}") from exc
