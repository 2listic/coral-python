"""The host's error types, in a leaf module both stages that raise them can import.

``DuplicateNodeTypeError`` is detected in two different places, which is why it lives here rather
than in either of them:

* stage 1 (:mod:`coral_app`) — two plugins declaring the same *function* name, or a plugin claiming
  one of the host's ``BUILTIN_FUNCTIONS``;
* stage 2 (:mod:`coral_app.nodeports`) — one name claimed by two *different kinds* of node, which
  stage 1 cannot see because the function and class surfaces are merged into separate maps.

It is re-exported from :mod:`coral_app`, so ``coral_app.DuplicateNodeTypeError`` remains the public
name; nothing imports this module for its own sake.
"""

__all__ = ["DuplicateNodeTypeError"]


class DuplicateNodeTypeError(ValueError):
    """Two contributors declared the same node type.

    A graph names only the node type, so a name with two owners is unresolvable *from the graph*:
    whichever callable ran, the graph looks identical. The host therefore refuses the selection
    instead of picking a winner. ``ValueError``, like the graph-validation errors, because it is a
    bad configuration; an unknown *plugin* name stays a ``LookupError``.
    """
