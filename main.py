import argparse

from registry import save_registry_to_file
from executor import WorkflowExecutor


def main():
    """Main entry point for the Coral workflow system"""
    parser = argparse.ArgumentParser(description='Execute a workflow from a JSON file')
    parser.add_argument('workflow_file',
        nargs='?',  # Makes it optional
        default='network-from-fe.json',
        help='Path to the workflow JSON file (default: network-py-mwe.json)'
    )

    # Add option to generate registry
    parser.add_argument('--generate-registry',
        action='store_true',
        help='Generate the registry file from FUNCTION_MAP'
    )
    parser.add_argument('--registry-output',
        default='registry-py-mwe.json',
        help='Output path for the registry file (default: registry-py-mwe.json)'
    )

    args = parser.parse_args()

    # Generate registry if requested
    if args.generate_registry:
        save_registry_to_file(args.registry_output)
    else:
        # Normal workflow execution
        executor = WorkflowExecutor(args.workflow_file)
        results = executor.execute()
        print(f"\nFinal results: {results}")


if __name__ == "__main__":
    main()
