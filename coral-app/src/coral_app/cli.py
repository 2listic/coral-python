"""Coral-compatible CLI for the Python backend.

Presents the same command surface as the reference ``coral`` binary so the DealiiX platform can
drive this backend by changing only the executable and plugin paths:

    coral -p <plugin> register           # write the node registry (node_types.json) into the cwd
    coral -p <plugin> run <graph.json>    # execute a workflow graph
    coral plugins                         # list the installed plugins, one name per line

For this Python backend ``-p/--plugin`` names the plugins to load (comma-separated, e.g.
``"math,string"``); an empty value loads every installed plugin (via entry-point discovery).
``-p/--plugin`` must appear before the subcommand; a name that is not installed, or one given
twice, is refused before any subcommand runs. Exposed as the ``coral`` console script and wrapped
by the ``coral-py`` launcher.
"""

import argparse

from coral_app import discover
from coral_app.executor import WorkflowExecutor
from coral_app.registry import save_registry_to_file

# Fixed filename the DealiiX platform probes for after `register`.
DEFAULT_REGISTRY_FILENAME = "node_types.json"

# Where per-node status markers go when `--touch-dir` is omitted: the cwd, as in the reference
# backend.
DEFAULT_TOUCH_DIR = "./"


def main():
    """Parse coral-style CLI arguments and dispatch to the ``register`` or ``run`` subcommand.

    The top-level parser owns the global ``-p/--plugin`` option (mirroring coral's plugin flag);
    ``register`` and ``run`` are subcommands. ``register`` writes the node registry to a JSON file
    in the current working directory; ``run`` executes a workflow graph via ``WorkflowExecutor``.
    """
    parser = argparse.ArgumentParser(
        prog="coral",
        description="Coral-compatible CLI: generate the node registry or run a workflow graph.",
    )
    # Global option mirroring coral's plugin flag. For the Python backend it names the plugins to
    # load (comma-separated); an empty value means "load every installed plugin".
    parser.add_argument(
        "-p",
        "--plugin",
        default="",
        metavar="PLUGINS",
        help="Comma-separated plugins to load (e.g. 'math,string'); empty loads all installed. "
        "Must precede the subcommand.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    register_parser = subparsers.add_parser(
        "register",
        help="Generate the node registry and write it to a JSON file in the current directory.",
    )
    register_parser.add_argument(
        "--output",
        default=DEFAULT_REGISTRY_FILENAME,
        help=f"Registry output filename, relative to the cwd (default: {DEFAULT_REGISTRY_FILENAME}).",
    )

    run_parser = subparsers.add_parser("run", help="Execute a workflow graph from a JSON file.")
    run_parser.add_argument(
        "graph",
        help="Path to the workflow JSON graph to execute.",
    )
    # The reference backend defaults this to "./" and has no "write nothing" mode, so the platform's
    # contract — which is this CLI — keeps that: omit the flag and the markers land in the cwd.
    # `nargs="?"` with the same const accepts a bare `--touch-dir`. Writing nothing at all is
    # reachable only from `WorkflowExecutor(touch_dir=None)`.
    run_parser.add_argument(
        "--touch-dir",
        default=None,
        nargs="?",
        const=None,
        metavar="PATH",
        help="Output directory for touch files (node status markers): one empty "
        f"<qualified_id>.running / .succeeded / .failed per node (default: {DEFAULT_TOUCH_DIR}). "
        "Existing markers in it are removed before the run.",
    )

    subparsers.add_parser(
        "plugins",
        help="List the installed plugins, one name per line: the values -p accepts.",
    )

    args = parser.parse_args()
    plugins = _resolve_plugins(parser, args.plugin)

    if args.command == "register":
        save_registry_to_file(args.output, plugins=plugins)
    elif args.command == "run":
        if args.touch_dir is None:
            print(f"No argument '--touch-dir' is given, default to {DEFAULT_TOUCH_DIR}.")
            args.touch_dir = DEFAULT_TOUCH_DIR
        executor = WorkflowExecutor(args.graph, plugins=plugins, touch_dir=args.touch_dir)
        results = executor.execute()
        print(f"\nFinal results: {results}")
    elif args.command == "plugins":
        for name in discover():
            print(name)


# ── Private helpers ──


def _resolve_plugins(parser, plugin_value):
    """Resolve the ``-p/--plugin`` value into an explicit list of plugin names.

    Splits a comma-separated value into plugin names, ignoring blank entries. An empty or
    whitespace-only value resolves to every installed plugin (``discover()``). This matches the
    ``None`` default of ``save_registry_to_file`` / ``WorkflowExecutor`` (both also fall back to
    every discovered plugin); it is resolved here explicitly so the loaded set is logged verbatim.

    Every name must be installed and given once; otherwise this exits through ``parser.error``
    (usage on stderr, status 2), naming every offending plugin at once. It runs before any
    subcommand: ``load`` would refuse an unknown name too, but only partway through building the
    maps — after ``run`` has already prepared the touch directory.
    """
    plugins = [p.strip() for p in plugin_value.split(",") if p.strip()]
    installed = discover()
    if not plugins:
        return installed

    unknown = [name for name in dict.fromkeys(plugins) if name not in installed]
    if unknown:
        parser.error(
            f"unknown {_plugins_word(unknown)} {_quoted(unknown)} "
            f"(installed: {', '.join(installed) or 'none'})"
        )
    repeated = [name for name in dict.fromkeys(plugins) if plugins.count(name) > 1]
    if repeated:
        parser.error(f"{_plugins_word(repeated)} {_quoted(repeated)} named more than once")
    return plugins


def _plugins_word(names):
    """``"plugin"`` or ``"plugins"``, agreeing with ``names``."""
    return "plugin" if len(names) == 1 else "plugins"


def _quoted(names):
    """The names, quoted and comma-separated, in the order given."""
    return ", ".join(repr(name) for name in names)


if __name__ == "__main__":
    main()
