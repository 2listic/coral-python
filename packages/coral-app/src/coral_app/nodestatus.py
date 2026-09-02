"""Per-node execution status markers, and the filenames they are written under.

The platform watches a directory while a graph runs and reads the timeline off it: one empty file
per node per state, listed with ``ls -tr``, so file mtime order *is* the order the nodes ran. This
module owns both halves of that convention — which name a node's files get, and when each file
appears — because both are the file format of one external consumer, and the executor should no more
know them than it knows the registry's JSON layout.

It is deliberately ignorant of graphs and of execution: :func:`qualified_ids` takes a plain mapping,
:class:`NodeStatusDir` takes a path, and neither imports anything from :mod:`coral_app.graph` or
:mod:`coral_app.executor`.

Written to match the reference backend, which is the producer the platform's consumer was written
against: the same three suffixes, the same cleanup at startup, and the same asymmetry between a setup
failure (fatal) and a failed touch mid-run (silent there, warned once here).

It diverges from that backend on one point, deliberately: the reference backend invents a
``<node_id>_auto_<counter>`` name for a node that declares no ``qualified_id`` and warns; here a
missing ``qualified_id`` is a :exc:`ValueError`. An invented name is not the node's identity — the
platform's, through nested subgraphs, is — so a graph that omits it gets a timeline the platform
cannot key back to its nodes.
Failing at t=0 says so; auto-naming hides it until someone reads the marker files.
"""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Generator, Mapping, Union

__all__ = ["FAILED", "RUNNING", "STATUS_SUFFIXES", "SUCCEEDED", "NodeStatusDir", "qualified_ids"]

RUNNING = ".running"
SUCCEEDED = ".succeeded"
FAILED = ".failed"

#: The three suffixes this module writes — and therefore the only files it removes when cleaning a
#: directory it did not create.
STATUS_SUFFIXES = (RUNNING, SUCCEEDED, FAILED)


def qualified_ids(nodes: Mapping[str, dict]) -> Dict[str, str]:
    """Map each node id to the qualified id its status files are named after.

    Every node must declare a ``qualified_id``, and it is used verbatim: on the platform that string
    is the node's path through nested subgraphs (``12_3`` is node 3 of the subnetwork at node 12),
    which is why the field exists at all. Node ids are unique only within one ``nodes`` object, so
    nothing here derives a qualified id from one — the two name different things, and only the
    qualified id is unique across nesting levels.

    Because the value becomes a *filename*, it must be a string that can be one. Four rejections,
    each of them a way for two nodes to end up writing the same markers, or for the consumer to
    read the wrong node's:

    - **not a string.** ``12`` and ``"12"`` are distinct as dict values but name one file, so a
      graph declaring both would lose a node from the timeline and bump the other's mtime. The
      reference backend cannot express this — its JSON accessor throws on a number.
    - **empty.** It would write ``.running``, a dotfile with no node name in it. (The reference
      backend falls back to the node id here; we do not, for the same reason we reject a missing
      field.)
    - **contains a ``.``** — the consumer splits each filename on ``.`` to recover the node, so a
      dot inside the name mis-keys it.
    - **contains a path separator.** ``top/first`` writes into a subdirectory the platform is not
      watching, or fails outright.

    Args:
        nodes: Node id -> node definition, in graph-JSON order.

    Returns:
        Node id -> qualified id, one entry per node.

    Raises:
        ValueError: if a node declares no ``qualified_id``, declares one that cannot be a filename,
            or repeats another's. Two nodes sharing a filename would corrupt the very timeline these
            files exist to show, and silently.
    """
    assigned: Dict[str, str] = {}
    seen = set()

    for node_id, node in nodes.items():
        declared = node.get("qualified_id")

        if declared is None:
            raise ValueError(
                f"Node {node_id!r} declares no qualified_id; every node must declare one, since "
                f"it is the name its execution status files are written under"
            )

        if not isinstance(declared, str):
            raise ValueError(
                f"Node {node_id!r} declares qualified_id {declared!r} of type "
                f"{type(declared).__name__}; it must be a string, since it names a file — "
                f"{declared!r} and {str(declared)!r} would write the same one"
            )

        if not declared:
            raise ValueError(
                f"Node {node_id!r} declares an empty qualified_id; it names this node's status "
                f"files, so it must be something the platform can read a node out of"
            )

        forbidden = [character for character in (".", "/", "\\") if character in declared]
        if forbidden:
            raise ValueError(
                f"Node {node_id!r} declares qualified_id {declared!r}, which contains "
                f"{', '.join(repr(character) for character in forbidden)}; a status filename is "
                f"split on '.' by the consumer and a path separator would leave the watched "
                f"directory"
            )

        if declared in seen:
            raise ValueError(
                f"Node {node_id!r} repeats qualified_id {declared!r}, which another node "
                f"already declares; qualified ids must be unique"
            )

        seen.add(declared)
        assigned[node_id] = declared

    return assigned


class NodeStatusDir:
    """The directory the status markers are written into, and the writing of them.

    Constructing one prepares the directory: it is created if missing, and otherwise emptied of the
    files this module writes — nothing else in it is touched, since the platform points us at a job
    directory it owns and a coral run in a checkout points us at the cwd. A stale timeline from an
    earlier job would be read as this job's, so the cleanup is not optional.

    The two failure modes are deliberately asymmetric (and the reference backend agrees):

    - preparing the directory raises. A bad ``--touch-dir`` is a configuration error, and it costs
      nothing to fail on it before the first node runs.
    - a touch that fails once nodes are running warns — once — and is otherwise ignored. By then the
      graph's result is worth more than its telemetry.
    """

    def __init__(self, directory: Union[str, os.PathLike]):
        """Create the directory if needed, else remove the status files already in it.

        Args:
            directory: Where the markers go. Parents are created as needed.

        Raises:
            OSError: if the directory cannot be created, listed, or cleaned.
        """
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._warned = False

        for entry in self.directory.iterdir():
            if entry.is_file() and entry.name.endswith(STATUS_SUFFIXES):
                entry.unlink()

    @contextmanager
    def node(self, qualified_id: str) -> Generator[None, None, None]:
        """Bracket one node's execution with its status markers.

        Entering writes ``<qualified_id>.running``; leaving normally writes ``.succeeded``; an
        exception escaping the block writes ``.failed`` and then propagates untouched — the type and
        the message a caller sees must not depend on whether a touch directory was configured.

        As in the reference backend, a failed node keeps its ``.running`` file: the pair is what
        tells the platform which node was in flight when the run died.

        Args:
            qualified_id: The name the three files are built from.
        """
        self._touch(qualified_id, RUNNING)
        try:
            yield
        except BaseException:
            self._touch(qualified_id, FAILED)
            raise
        self._touch(qualified_id, SUCCEEDED)

    # ── Private helpers ──

    def _touch(self, qualified_id: str, suffix: str) -> None:
        """Create one empty marker file, warning at most once if the filesystem refuses.

        No name is ever written twice in a run — the three suffixes differ and the directory was
        cleaned at startup — so ``touch()`` always creates the file, and its mtime is the moment the
        node reached that state. That is what the consumer's ``ls -tr`` ordering rests on.
        """
        try:
            (self.directory / f"{qualified_id}{suffix}").touch()
        except OSError as error:
            if not self._warned:
                self._warned = True
                print(
                    f"Warning: cannot write execution status files in {self.directory}: {error}. "
                    f"Execution continues; the status timeline will be incomplete."
                )
