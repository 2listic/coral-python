"""What this package's tests share, in a module with a name no other package uses.

Why not ``conftest.py``: with ``--import-mode=importlib`` a test module doing ``from conftest import X``
goes through the normal import system, where the module name ``conftest`` is global — so the four
packages' conftests would resolve to whichever was imported first. pytest handles its *own* conftest
loading correctly; a plain import of it does not. Anything needed at **collection** time (a path to
parametrise graph files over) cannot be a fixture, so it lives here instead.
"""

from pathlib import Path
from typing import Callable, Dict, Iterable

from coral_core import ClassDeclaration, Declaration, Plugin

#: The examples this package ships — the collection graphs, which need no plugin.
EXAMPLES = Path(__file__).parent.parent / "examples"


def declared_functions(functions: Dict[str, Callable]) -> Dict[str, Declaration]:
    """``{node type: function}`` as the function map the host builds: each function declared, under
    its key, on a fresh plugin."""
    plugin = Plugin()
    for node_type, func in functions.items():
        plugin.function(func, name=node_type)
    return plugin.functions()


def declared_classes(
    classes: Dict[str, type], methods: Iterable[Callable] = ()
) -> Dict[str, ClassDeclaration]:
    """``{class key: class}`` as the class map the host builds: each class declared, under its key,
    on a fresh plugin, with ``methods`` declared as their method nodes, each ``const=True``: the
    shapes the callers check are a reader's, and a writer's are tested on their own."""
    plugin = Plugin()
    for method in methods:
        plugin.method(method, const=True)
    for key, cls in classes.items():
        plugin.cls(cls, name=key)
    return plugin.classes()
