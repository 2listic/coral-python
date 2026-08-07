"""Constants this package's tests share, in a module with a name no other package uses.

Why not ``conftest.py``: with ``--import-mode=importlib`` a test module doing ``from conftest import X``
goes through the normal import system, where the module name ``conftest`` is global — so the four
packages' conftests would resolve to whichever was imported first. pytest handles its *own* conftest
loading correctly; a plain import of it does not. Anything needed at **collection** time (a path to
parametrise graph files over) cannot be a fixture, so it lives here instead.
"""

from pathlib import Path

#: Where the host suite's own graphs live.
GRAPHS = Path(__file__).parent / "graphs"

#: The examples this package ships — the collection graphs, which need no plugin.
EXAMPLES = Path(__file__).parent.parent / "examples"
