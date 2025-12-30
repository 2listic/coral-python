import argparse

from registry import save_registry_to_file
from executor import WorkflowExecutor


def main():
    """Main entry point for the Coral workflow system"""
    parser = argparse.ArgumentParser(description='Execute a workflow from a JSON file')
    parser.add_argument('workflow_file',
        nargs='?',  # Makes it optional
        default='network-from-fe.json',
        help='Path to the workflow JSON file (default: network-from-fe.json)'
    )

    # Add option to generate registry
    parser.add_argument('--generate-registry',
        action='store_true',
        help='Generate the registry file from definitions.py'
    )
    parser.add_argument('--registry-output',
        default='registry-py.json',
        help='Output path for the registry file (default: registry-py.json)'
    )

    # Add option to specify which modules to load
    parser.add_argument('--modules',
        default='phiflow',
        help='Comma-separated list of modules to load (options: math, string, phiflow). Default: phiflow'
    )

    args = parser.parse_args()

    # Parse module list
    module_list = [m.strip() for m in args.modules.split(',') if m.strip()]

    # Generate registry if requested
    if args.generate_registry:
        save_registry_to_file(args.registry_output, modules=module_list)
    else:
        # Normal workflow execution
        executor = WorkflowExecutor(args.workflow_file, modules=module_list)
        results = executor.execute()
        print(f"\nFinal results: {results}")


if __name__ == "__main__":
    main()
