"""Rules about the repo's *source text*, checked by reading it.

Nothing here imports the code under test, runs a graph, or needs a plugin installed: every test
reads the repo's package directories and asserts something about what is written in them. A failure
here means **someone wrote a forbidden line** — the fix is always to change that line, never to
change the code's behaviour.

Three families of rule live here:

* **no ``from __future__ import annotations``** anywhere in package source — it stringizes
  annotations, and ``registry.py:python_type_to_string`` would collapse every socket to ``"any"``;
* **the stage boundaries** inside ``coral-app`` (issue #23): ``graph.py`` compares plain data,
  ``executor.py`` receives an already-validated graph;
* **the directional rules** (issue #27) that keep the separation principle from eroding — the host
  never reaches for a plugin, a plugin never reaches for the host, and the host's *tests* never name
  a plugin at all.

The plugin names come from ``plugins/coral-*`` on disk. That is not a catalog anyone maintains: it is
the set of plugin distributions the repo ships, read at run time, so adding a plugin extends these
rules automatically.

**The list of source roots is duplicated in two files this module cannot read**, and that is the one
duplication the layout cannot remove — neither ``uv`` nor ``pytest`` can read a Python constant:

===========================  ==============================================================
``pyproject.toml``           ``[tool.uv.workspace] members``, ``[tool.coverage.run] source``
``pytest.ini``               ``testpaths``
``SOURCE_ROOTS`` below       every rule in this module
===========================  ==============================================================

Adding a fourth root means editing all three. ``TestGuardsAreNotVacuous`` compares ``SOURCE_ROOTS``
against the distributions actually on disk, so forgetting *this* file fails loudly rather than
silently narrowing a guard.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE = REPO_ROOT / "coral-core"
HOST = REPO_ROOT / "coral-app"
PLUGINS = REPO_ROOT / "plugins"
PLUGIN_PREFIX = "coral-"

# Directories that hold no source of ours but do contain `pyproject.toml` files (dependencies) or
# stale copies (build output). Skipped when discovering distributions on disk.
NOT_OURS = {".venv", ".git", "dist", "build", "__pycache__", "issues", "node_modules"}


def source_roots() -> list:
    """Every distribution directory this repo ships: the two framework packages, then the plugins.

    Derived in **one** place, because four things used to rely on the single glob ``packages/*``
    meaning "every distribution". Now that the framework sits at the root and the plugins under
    ``plugins/``, a rule that listed the roots itself could silently cover fewer than all of them.
    """
    plugins = sorted(p for p in PLUGINS.glob(f"{PLUGIN_PREFIX}*") if p.is_dir())
    return [CORE, HOST] + plugins


SOURCE_ROOTS = source_roots()


def distributions_on_disk() -> set:
    """Every directory in the repo that is an installable distribution — it has its own pyproject.

    Deliberately derived a *different* way from :func:`source_roots`: by finding the manifests rather
    than by knowing where to look. That independence is what lets the vacuity test notice a package
    added somewhere nobody updated.
    """
    found = set()
    for manifest in REPO_ROOT.glob("**/pyproject.toml"):
        relative = manifest.relative_to(REPO_ROOT)
        if manifest.parent == REPO_ROOT:
            continue  # the virtual workspace root: wires the members, ships nothing
        if NOT_OURS & set(relative.parts):
            continue
        found.add(manifest.parent)
    return found


def repo_plugin_names() -> list:
    """Plugin names this repo ships, from ``plugins/coral-<name>`` (the source of truth).

    The directory name drops the word ``plugin`` that the distribution keeps, so ``coral-math`` here
    is distribution ``coral-plugin-math``, import package ``coral_plugin_math``, entry point ``math``
    (issue #27, L3–L5). It is the last of those four that these rules care about.
    """
    return sorted(p.name[len(PLUGIN_PREFIX) :] for p in PLUGINS.glob(f"{PLUGIN_PREFIX}*"))


def python_files(directory: Path) -> list:
    """Every ``.py`` file under *directory*, recursively."""
    return sorted(directory.glob("**/*.py"))


def imported_modules(path: Path) -> set:
    """The module names *path* imports, from both `import x` and `from x import y`."""
    tree = ast.parse(path.read_text(), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
    return modules


def string_constants(path: Path) -> set:
    """Every string literal in *path*, including docstrings."""
    tree = ast.parse(path.read_text(), filename=str(path))
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


class TestNoFutureAnnotations:
    """No package source may `from __future__ import annotations`."""

    def _package_sources(self):
        return [path for root in SOURCE_ROOTS for path in python_files(root)]

    def test_sources_present(self):
        """GIVEN the workspace packages
        WHEN their source files are collected
        THEN at least one Python source exists to guard."""
        assert self._package_sources(), "no package sources found to check"

    def test_no_future_annotations_import(self):
        """GIVEN every package source file
        WHEN its imports are parsed
        THEN none imports `annotations` from __future__."""
        offenders = []
        for path in self._package_sources():
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                    if any(alias.name == "annotations" for alias in node.names):
                        offenders.append(str(path))
        assert not offenders, f"forbidden `from __future__ import annotations` in: {offenders}"


class TestStageSeparation:
    """Issue #23: one job per module, enforced structurally rather than by convention.

    The refactor split the old executor into stages — describe node types (``nodeports``), validate
    and order a graph (``graph``), execute it (``executor``). These guards pin the boundaries that
    make each stage independently testable: ``graph.py`` compares plain data, so it never
    introspects a callable or reaches for a plugin; ``executor.py`` receives an already-validated
    graph, so it never parses JSON, sorts, or walks the edge list.

    Only each file's *own* imports are inspected. ``graph.py`` importing ``NodePorts`` for a type
    annotation is the intended dependency on stage 2, even though stage 2 uses ``inspect`` itself.
    """

    def _path(self, module_name):
        path = HOST / "src" / "coral_app" / f"{module_name}.py"
        assert path.exists(), f"missing module: {path}"
        return path

    def _source(self, module_name):
        return self._path(module_name).read_text()

    def _imports(self, module_name):
        """The modules and the symbols a file imports."""
        path = self._path(module_name)
        tree = ast.parse(path.read_text(), filename=module_name)
        modules, symbols = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.add(node.module or "")
                symbols.update(alias.name for alias in node.names)
        return modules, symbols

    def test_graph_does_not_introspect(self):
        """GIVEN graph.py
        WHEN its imports are parsed
        THEN `inspect` is absent — the port table arrives as plain data."""
        modules, _ = self._imports("graph")

        assert "inspect" not in modules

    def test_graph_does_not_reach_for_plugins(self):
        """GIVEN graph.py
        WHEN its imports are parsed
        THEN it imports no plugin and none of the host's plugin-loading machinery."""
        modules, symbols = self._imports("graph")

        assert not [name for name in modules if name.startswith("coral_plugin")]
        assert not symbols & {"discover", "load", "build_function_map", "build_class_map"}

    def test_executor_does_not_read_or_order_the_graph(self):
        """GIVEN executor.py
        WHEN its imports are parsed
        THEN neither `json` nor `graphlib` is there — reading and sorting belong to graph.py."""
        modules, _ = self._imports("executor")

        assert "json" not in modules
        assert "graphlib" not in modules

    def test_executor_never_holds_the_edge_list(self):
        """GIVEN executor.py
        WHEN its source is read
        THEN it holds no `self.edges` — it asks the graph for a node's inputs instead."""
        assert "self.edges" not in self._source("executor")


class TestDependencyDirection:
    """The declared dependency direction, read off the source: plugin -> core <- app.

    The host finds plugins through entry points at run time; a plugin is handed nothing but
    ``coral_core``. Neither side may name the other in an import, or the monorepo acquires a cycle
    that `uv` cannot see and a plugin author cannot break.
    """

    def test_plugin_sources_present(self):
        """GIVEN the workspace
        WHEN plugin packages are collected from disk
        THEN at least one exists to guard."""
        assert repo_plugin_names(), f"no {PLUGIN_PREFIX}* package found under {PLUGINS}"

    def test_host_never_imports_a_plugin(self):
        """GIVEN every coral-app source file
        WHEN its imports are parsed
        THEN none names a `coral_plugin_*` module — the host only discovers them at run time."""
        offenders = {}
        for path in python_files(HOST / "src"):
            named = {m for m in imported_modules(path) if m.startswith("coral_plugin")}
            if named:
                offenders[str(path.relative_to(REPO_ROOT))] = sorted(named)
        assert not offenders, f"coral-app must not import a plugin: {offenders}"

    def test_plugin_never_imports_the_host(self):
        """GIVEN every plugin's source files
        WHEN their imports are parsed
        THEN none names `coral_app` — a plugin depends on `coral_core` and nothing else of ours."""
        offenders = {}
        for name in repo_plugin_names():
            for path in python_files(PLUGINS / f"{PLUGIN_PREFIX}{name}" / "src"):
                named = {m for m in imported_modules(path) if m.split(".")[0] == "coral_app"}
                if named:
                    offenders[str(path.relative_to(REPO_ROOT))] = sorted(named)
        assert not offenders, f"a plugin must not import coral_app: {offenders}"


class TestHostTestsNameNoPlugin:
    """The separation principle, made executable: the host's own suite names no plugin.

    `coral-app`'s tests run against the designed specimen in `coral-app/tests/specimen.py`, so they
    pass with **zero** plugins installed and never skip. Three ways a plugin name could creep back in
    are checked; a plugin's own name inside its own `tests/` is fine and untouched here.

    The literal check compares a string for *equality* with a plugin name, so `"math.sqrt"` and the
    word "string" in prose do not trip it, while `build_function_map(include=["math"])` does.
    """

    HOST_TESTS = HOST / "tests"

    def _host_test_files(self):
        return python_files(self.HOST_TESTS) if self.HOST_TESTS.exists() else []

    def test_host_suite_never_imports_a_plugin(self):
        """GIVEN every file in coral-app's test suite
        WHEN its imports are parsed
        THEN none names a `coral_plugin_*` module."""
        offenders = {}
        for path in self._host_test_files():
            named = {m for m in imported_modules(path) if m.startswith("coral_plugin")}
            if named:
                offenders[str(path.relative_to(REPO_ROOT))] = sorted(named)
        assert not offenders, f"the host suite must not import a plugin: {offenders}"

    def test_host_suite_uses_no_plugin_marker(self):
        """GIVEN every file in coral-app's test suite
        WHEN its text is read
        THEN it applies no `mark.<plugin>` — nothing in it may be skipped for a missing plugin."""
        offenders = {}
        for path in self._host_test_files():
            source = path.read_text()
            used = [name for name in repo_plugin_names() if f"mark.{name}" in source]
            if used:
                offenders[str(path.relative_to(REPO_ROOT))] = used
        assert not offenders, f"the host suite must carry no plugin marker: {offenders}"

    def test_host_suite_names_no_plugin_in_a_literal(self):
        """GIVEN every file in coral-app's test suite
        WHEN its string literals are collected
        THEN none equals a plugin name — no `include=["math"]`, no `-p` selection."""
        names = set(repo_plugin_names())
        offenders = {}
        for path in self._host_test_files():
            named = string_constants(path) & names
            if named:
                offenders[str(path.relative_to(REPO_ROOT))] = sorted(named)
        assert not offenders, f"the host suite must not name a plugin: {offenders}"


class TestGuardsAreNotVacuous:
    """Every rule above must actually be reading something — the guard on the guards.

    Two distinct ways a rule in this module can stop protecting anything, and neither announces
    itself, because a grep that finds no files *passes*:

    * a directory it scans is **empty** or has moved — `test_scanned_directories_are_populated`;
    * ``SOURCE_ROOTS`` is **narrower than the repo** — a package was added, or moved, and this file
      was not updated. Before issue #27's step 9 one glob (``packages/*``) meant "every
      distribution"; now three roots are listed, here and in `pyproject.toml` and `pytest.ini`, so
      "someone extended two of the three" is a real way to silently drop a package from the
      ``__future__`` rule. `test_source_roots_cover_every_distribution` is the answer to that.
    """

    def test_scanned_directories_are_populated(self):
        """GIVEN the directories the source rules scan
        WHEN their Python files are collected
        THEN each holds at least one file."""
        scanned = {"coral-app/src": HOST / "src"}
        for name in repo_plugin_names():
            scanned[f"plugins/{PLUGIN_PREFIX}{name}/src"] = (
                PLUGINS / f"{PLUGIN_PREFIX}{name}" / "src"
            )

        empty = [label for label, path in scanned.items() if not python_files(path)]
        assert not empty, f"source rules would scan nothing in: {empty}"

    def test_source_roots_cover_every_distribution(self):
        """GIVEN the distributions on disk, found by their own pyproject.toml
        WHEN compared with the SOURCE_ROOTS these rules scan
        THEN the two sets are equal — no package escapes the source rules."""
        expected = {path.relative_to(REPO_ROOT).as_posix() for path in distributions_on_disk()}
        scanned = {path.relative_to(REPO_ROOT).as_posix() for path in SOURCE_ROOTS}

        assert scanned == expected, (
            "SOURCE_ROOTS and the repo disagree about which distributions exist. "
            f"unscanned: {sorted(expected - scanned)}; missing from disk: {sorted(scanned - expected)}. "
            "Update SOURCE_ROOTS here, and `members`/`source` in pyproject.toml and `testpaths` "
            "in pytest.ini with it."
        )

    def test_host_test_suite_is_scanned(self):
        """GIVEN coral-app's test directory
        WHEN its Python files are collected
        THEN at least one exists, so the host-suite rules guard something."""
        assert python_files(HOST / "tests"), f"no test files under {HOST / 'tests'}"
