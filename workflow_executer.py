import json
from typing import Any, Dict, List


# Define the functions that can be called by nodes
def add(a: float, b: float) -> float:
    """Add two numbers"""
    result = a + b
    print(f"add({a}, {b}) = {result}")
    return result


def multiply(value: float, x: float) -> float:
    """Multiply a value by x"""
    result = value * x
    print(f"multiply({value}, {x}) = {result}")
    return result


def print_result(value: float, message: str) -> float:
    """Print the result with a message"""
    print(f"{message}: {value}")
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
        
        self.nodes = {node['id']: node for node in data['nodes']}
        self.edges = data['edges']
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
            func_name = node['function']
            params = node['params'].copy()
            
            # If this node has incoming edges, pass the result from previous node
            incoming = [e for e in self.edges if e['to'] == node_id]
            if incoming:
                # Get result from the last incoming node
                prev_node_id = incoming[0]['from']
                if prev_node_id in self.results:
                    params['value'] = self.results[prev_node_id]
            
            # Execute the function
            func = FUNCTION_MAP[func_name]
            result = func(**params)
            self.results[node_id] = result
            print()
        
        print(f"All nodes executed successfully!")
        return self.results


if __name__ == "__main__":
    executor = WorkflowExecutor("workflow.json")
    results = executor.execute()
    print(f"\nFinal results: {results}")