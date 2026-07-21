"""Coral-compatible CLI for the Python backend.

Presents the same command surface as the C++ ``coral`` binary so the DealiiX platform can drive this
backend by changing only the executable and plugin paths:

    coral -p <plugin> register           # write the node registry (node_types.json) into the cwd
    coral -p <plugin> run <graph.json>    # execute a workflow graph

For this Python backend ``-p/--plugin`` names the plugins to load (comma-separated, e.g.
``"math,string"``); an empty value loads every installed plugin (via entry-point discovery).
``-p/--plugin`` must appear before the subcommand. Exposed as the ``coral`` console script and
wrapped by the ``coral-py`` launcher. See the integration plan in issue #12.
"""

import argparse

from coral_app import discover
from coral_app.registry import save_registry_to_file
from coral_app.executor import WorkflowExecutor

# Fixed filename the DealiiX platform probes for after `register`.
DEFAULT_REGISTRY_FILENAME = "node_types.json"
# Workflow used when `run` is given no graph argument (keeps the pre-refactor default reachable).
DEFAULT_WORKFLOW_FILE = "network-from-fe.json"


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
        "-p", "--plugin",
        default="",
        metavar="MODULES",
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
        nargs="?",
        default=DEFAULT_WORKFLOW_FILE,
        help=f"Path to the workflow JSON graph (default: {DEFAULT_WORKFLOW_FILE}).",
    )
    run_parser.add_argument(
        "--touch-dir",
        default=None,
        help="Directory for per-node status files. Accepted for coral compatibility; not yet emitted.",
    )

    args = parser.parse_args()
    modules = _resolve_modules(args.plugin)

    if args.command == "register":
        save_registry_to_file(args.output, modules=modules)
    elif args.command == "run":
        executor = WorkflowExecutor(args.graph, modules=modules)
        results = executor.execute()
        print(f"\nFinal results: {results}")


# ── Private helpers ──


def _resolve_modules(plugin_value):
    """Resolve the ``-p/--plugin`` value into an explicit list of plugin names.

    Splits a comma-separated value into plugin names, ignoring blank entries. An empty or
    whitespace-only value resolves to every installed plugin (``discover()``) — this is passed
    explicitly (rather than relying on ``None``) because ``save_registry_to_file``/
    ``WorkflowExecutor`` default a ``None`` module list to ``['phiflow']`` only.
    """
    modules = [m.strip() for m in plugin_value.split(",") if m.strip()]
    return modules if modules else discover()


if __name__ == "__main__":
    main()
