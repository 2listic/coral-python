import argparse
import json
from typing import Any, Dict, List
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


def print_result(value: Any) -> Any:
    """Print the result with a message"""
    print(f"Print: {value}")
    return value


# Map function names to actual functions
FUNCTION_MAP = {
    "add": add,
    "multiply": multiply,
    "print_result": print_result
}


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
            node_type = node.get('type', 'function')
            
            if node_type == 'elementary':
                # Elementary nodes just return their value
                result = node['value']
                self.results[node_id] = result
                print(f"{node_id} (elementary) = {result}")
            
            elif node_type == 'function':
                # Function nodes execute a function with inputs from edges
                func_name = node['function']
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
                raise ValueError(f"Unknown node type: {node_type}")
            
            print()
        
        print(f"All nodes executed successfully!")
        return self.results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Execute a workflow from a JSON file')
    parser.add_argument('workflow_file', 
        nargs='?',  # Makes it optional
        default='workflow_mwe.json',
        help='Path to the workflow JSON file (default: workflow_mwe.json)'
    )
    
    args = parser.parse_args()
    
    executor = WorkflowExecutor(args.workflow_file)
    results = executor.execute()
    print(f"\nFinal results: {results}")