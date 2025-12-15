import argparse
import json
from typing import Any, Dict, List, get_type_hints, get_origin
import inspect


# Define the functions that can be called by nodes
def add(a: float, b: float) -> float:
    """Add two numbers"""
    result = a + b
    print(f"add({a}, {b}) = {result}")
    return result


def multiply(a: float, b: float) -> float:
    """Multiply a by b"""
    result = a * b
    print(f"multiply({a}, {b}) = {result}")
    return result


def print_result(value: Any) -> None:
    """Print the result with a message"""
    print(f"Print: {value}")


# Map function names to actual functions
FUNCTION_MAP = {
    "add": add,
    "multiply": multiply,
    "print_result": print_result
}


PRIMITIVES = ["int", "float", "str", "bool", "any"]


def generate_registry(function_map: Dict[str, callable], primitives: List[str] = None) -> Dict:
    """Generate a registry JSON from function definitions"""
    
    if (primitives is None or function_map is None):
        raise ValueError("primitives and function_map must be provided")
    
    registry = {}
    node_id = 0
    
    # Add primitive types
    for prim_type in primitives:
        registry[str(node_id)] = {
            "value": None,
            "inputs": [],
            "outputs": [-1],
            "node_type": "primitive",
            "type": prim_type
        }
        node_id += 1
    
    # Add functions
    for func_name, func in function_map.items():
        # Get function signature and type hints
        sig = inspect.signature(func)
        try:
            type_hints = get_type_hints(func)
        except Exception:
            # Fallback if type hints can't be resolved
            type_hints = {}
        
        arguments = []
        inputs = []
        
        # Process input parameters
        param_idx = 0
        for param_name, param in sig.parameters.items():
            # Get type from hints or annotation
            param_type = type_hints.get(param_name, param.annotation)
            json_type = python_type_to_json_type(param_type)
            
            arguments.append({
                "connection_type": "input",
                "type": json_type
            })
            inputs.append(param_idx)
            param_idx += 1
        
        # Process return type (output)
        return_type = type_hints.get('return', sig.return_annotation)
        return_json_type = python_type_to_json_type(return_type)
        
        # Only add output if function returns something (not None)
        if return_type is not None and return_type != type(None) and return_type != inspect.Signature.empty:
            arguments.append({
                "connection_type": "output",
                "type": return_json_type
            })
            outputs = [param_idx]
        else:
            outputs = []
        
        registry[str(node_id)] = {
            "arguments": arguments,
            "inputs": inputs,
            "outputs": outputs,
            "node_type": "function",
            "method_name": func_name
        }
        node_id += 1
    
    return registry


def python_type_to_json_type(py_type) -> str:
    """Convert Python type annotation to JSON schema type string"""
    
    # Handle empty/missing annotations
    if py_type is inspect.Signature.empty or py_type is None:
        return "any"
    
    # Handle typing module types (like Any)
    if py_type is Any:
        return "any"
    
    # Handle basic types
    type_map = {
        int: "int",
        float: "float",
        str: "string",
        bool: "bool",
        type(None): "none"
    }
    
    if py_type in type_map:
        return type_map[py_type]
    
    # Handle typing generics (Optional, Union, etc.)
    origin = get_origin(py_type)
    if origin is not None:
        # For Optional, Union, etc., just return "any" for simplicity
        # You could make this more sophisticated
        return "any"
    
    # Default to "any" for unknown types
    return "any"


def save_registry_to_file(filename: str = "registry-py-mwe.json"):
    """Generate and save the registry to a JSON file"""
    registry = generate_registry(FUNCTION_MAP, PRIMITIVES)
    
    with open(filename, 'w') as f:
        json.dump(registry, f, indent=2)
    
    print(f"Registry saved to {filename}")
    return registry


class WorkflowExecutor:
    def __init__(self, workflow_file: str):
        with open(workflow_file, 'r') as f:
            data = json.load(f)
        
        self.nodes = {}
        for node_id, node_data in data['nodes'].items():
            self.nodes[node_id] = node_data
        self.edges = list(data['edges'].values())
        self.results = {}
    
    def get_execution_order(self) -> List[str]:
        """Determine execution order using topological sort"""
        # Build adjacency list
        graph = {node_id: [] for node_id in self.nodes.keys()}
        in_degree = {node_id: 0 for node_id in self.nodes.keys()}
        
        for edge in self.edges:
            graph[edge['from']].append(edge['to'])
            in_degree[edge['to']] += 1
        
        # Topological sort using Kahn's algorithm
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        order = []
        
        while queue:
            node_id = queue.pop(0)
            order.append(node_id)
            
            for neighbor in graph[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        if len(order) != len(self.nodes):
            raise ValueError("Cycle detected in workflow!")
        
        return order
    
    def execute(self):
        """Execute the workflow"""
        order = self.get_execution_order()
        print(f"Execution order: {order}\n")
        
        for node_id in order:
            node = self.nodes[node_id]
            node_type = node.get('node_type', 'function')
            
            if node_type == 'primitive':
                # Elementary nodes just return their value
                result = node['value']
                self.results[node_id] = result
                print(f"{node_id} (primitive) = {result}")
            
            elif node_type == 'function':
                # function nodes execute a function with inputs from edges
                func_name = node['method_name']
                func = FUNCTION_MAP[func_name]
                
                # Get incoming edges for this node
                incoming_edges = [e for e in self.edges if e['to'] == node_id]
                
                # Collect inputs based on target_input index
                # Sort by target_input to maintain proper parameter order
                incoming_edges.sort(key=lambda e: e['target_input'])
                
                # Build the input list
                inputs = []
                for edge in incoming_edges:
                    source_node_id = edge['from']
                    if source_node_id not in self.results:
                        raise ValueError(f"Node {source_node_id} hasn't been executed yet!")
                    inputs.append(self.results[source_node_id])
                
                # Get function parameter names
                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())
                
                # Map inputs to parameters
                if len(inputs) != len(param_names):
                    raise ValueError(
                        f"Function {func_name} expects {len(param_names)} parameters "
                        f"but received {len(inputs)} inputs"
                    )
                
                # Create kwargs dict
                kwargs = {param_names[i]: inputs[i] for i in range(len(inputs))}
                
                # Execute the function
                result = func(**kwargs)
                self.results[node_id] = result
            
            else:
                raise ValueError(f"Unknown node node_type: {node_type}")
            
            print()
        
        print(f"All nodes executed successfully!")
        return self.results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Execute a workflow from a JSON file')
    parser.add_argument('workflow_file', 
        nargs='?',  # Makes it optional
        default='network-py-mwe.json',
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