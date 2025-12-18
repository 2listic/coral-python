import json
import inspect
from typing import Any, List

from definitions import FUNCTION_MAP, PRIMITIVES_MAP, CLASS_MAP


class WorkflowExecutor:
    def __init__(self, workflow_file: str):
        with open(workflow_file, "r") as f:
            data = json.load(f)

        self.nodes = {}
        for node_id, node_data in data["workflow"]["nodes"].items():
            self.nodes[node_id] = node_data

        self.edges = []
        for edge_data in data["workflow"]["edges"].values():
            edge = edge_data.copy()
            edge["source"] = str(edge["source"])
            edge["target"] = str(edge["target"])
            self.edges.append(edge)

        self.results = {}

    def get_execution_order(self) -> List[str]:
        """Determine execution order using topological sort"""
        # Build adjacency list
        graph = {node_id: [] for node_id in self.nodes.keys()}
        in_degree = {node_id: 0 for node_id in self.nodes.keys()}

        for edge in self.edges:
            graph[edge["source"]].append(edge["target"])
            in_degree[edge["target"]] += 1

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
            node_type = node.get("node_type", "function")

            if node_type == "primitive":
                # Elementary nodes just return their value with type conversion
                raw_value = node["value"]
                prim_type = node.get("type", "any")

                # Convert value based on type using PRIMITIVES_MAP
                if prim_type in PRIMITIVES_MAP:
                    converter = PRIMITIVES_MAP[prim_type]
                    if converter is type(None):
                        result = None
                    elif converter is Any: # Don't convert value if type is Any
                        result = raw_value
                    else: # Cast value to correct type (may be a string in the JSON protocol)
                        result = converter(raw_value)
                else:  # Not found type
                    raise ValueError(f"Not found primitive type: {prim_type}")

                self.results[node_id] = result
                print(f"{node_id} (primitive) = {result}")

            elif node_type == "function":
                # function nodes execute a function with inputs source edges
                func_name = node["method_name"]
                func = FUNCTION_MAP[func_name]

                # Get incoming edges for this node
                incoming_edges = [e for e in self.edges if e["target"] == node_id]

                # Collect inputs based on target_input index
                # Sort by target_input to maintain proper parameter order
                incoming_edges.sort(key=lambda e: e["target_input"])

                # Build the input list
                inputs = []
                for edge in incoming_edges:
                    source_node_id = edge["source"]
                    if source_node_id not in self.results:
                        raise ValueError(
                            f"Node {source_node_id} hasn't been executed yet!"
                        )
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

            elif node_type == "constructor":
                # Constructor nodes instantiate a class
                class_name = node["class_name"]
                cls = CLASS_MAP[class_name]

                # Get incoming edges for constructor parameters
                incoming_edges = [e for e in self.edges if e["target"] == node_id]
                incoming_edges.sort(key=lambda e: e["target_input"])

                # Collect inputs
                inputs = []
                for edge in incoming_edges:
                    source_node_id = edge["source"]
                    if source_node_id not in self.results:
                        raise ValueError(
                            f"Node {source_node_id} hasn't been executed yet!"
                        )
                    inputs.append(self.results[source_node_id])

                # Get constructor parameter names (skip 'self')
                init_sig = inspect.signature(cls.__init__)
                param_names = [name for name in init_sig.parameters.keys() if name != 'self']

                # Map inputs to parameters
                if len(inputs) != len(param_names):
                    raise ValueError(
                        f"Constructor {class_name} expects {len(param_names)} parameters "
                        f"but received {len(inputs)} inputs"
                    )

                # Create kwargs dict
                kwargs = {param_names[i]: inputs[i] for i in range(len(inputs))}

                # Instantiate the class
                instance = cls(**kwargs)
                self.results[node_id] = instance
                print(f"{node_id} (constructor {class_name}) = {instance}")

            elif node_type == "method":
                # Method nodes call an instance method
                class_name = node["class_name"]
                method_name = node["method_name"]

                # Get incoming edges
                incoming_edges = [e for e in self.edges if e["target"] == node_id]
                incoming_edges.sort(key=lambda e: e["target_input"])

                # First input must be the instance
                if len(incoming_edges) == 0:
                    raise ValueError(f"Method node {node_id} has no instance input!")

                # Collect all inputs (first is instance, rest are method parameters)
                inputs = []
                for edge in incoming_edges:
                    source_node_id = edge["source"]
                    if source_node_id not in self.results:
                        raise ValueError(
                            f"Node {source_node_id} hasn't been executed yet!"
                        )
                    inputs.append(self.results[source_node_id])

                # Extract instance and method parameters
                instance = inputs[0]
                method_inputs = inputs[1:]

                # Verify instance is of correct class
                if not isinstance(instance, CLASS_MAP[class_name]):
                    raise ValueError(
                        f"Method node {node_id} expected instance of {class_name}, "
                        f"got {type(instance).__name__}"
                    )

                # Get the method from the instance
                method = getattr(instance, method_name)

                # Get method parameter names (skip 'self')
                sig = inspect.signature(method)
                param_names = [name for name in sig.parameters.keys() if name != 'self']

                # Map method inputs to parameters
                if len(method_inputs) != len(param_names):
                    raise ValueError(
                        f"Method {class_name}.{method_name} expects {len(param_names)} parameters "
                        f"but received {len(method_inputs)} inputs"
                    )

                # Create kwargs dict
                kwargs = {param_names[i]: method_inputs[i] for i in range(len(method_inputs))}

                # Execute the method
                result = method(**kwargs)
                self.results[node_id] = result

            else:
                raise ValueError(f"Unknown node type: {node_type}. Supported types: primitive, function, constructor, method")

            print()

        print(f"All nodes executed successfully!")
        return self.results
