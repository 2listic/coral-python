import json
import inspect
from typing import Any, List, Optional

from coral_app import PRIMITIVES_MAP, build_function_map, build_class_map


class WorkflowExecutor:
    def __init__(self, workflow_file: str, modules: Optional[List[str]] = None):
        """Initialize the workflow executor

        Args:
            workflow_file: Path to the workflow JSON file
            modules: List of module names to load. If None, defaults to ['phiflow']
        """
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

        # Build function and class maps based on specified modules
        if modules is None:
            modules = ['phiflow']

        self.function_map = build_function_map(include=modules)
        self.class_map = build_class_map(include=modules)
        self.primitives_map = PRIMITIVES_MAP

        print(f"Loaded modules: {', '.join(modules)}")
        print(f"Available functions: {len(self.function_map)}")
        print(f"Available classes: {len(self.class_map)}\n")

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

    def _classify(self, type_str: str) -> str:
        """Infer a node's kind from its ``type`` using the loaded definition maps.

        The graph protocol identifies every node by ``type`` (primitives by type name, functions by
        name, constructors by class name, methods by ``Class.method``); the kind is derived here
        rather than read from the node, so lean graphs that omit ``node_type`` behave the same as
        full ones. Functions are checked before the method split so dotted names like ``math.sqrt``
        resolve as functions, not methods.

        Raises:
            ValueError: if ``type_str`` matches no loaded primitive, function, class, or method.
        """
        if type_str in self.primitives_map:
            return "primitive"
        if type_str in self.function_map:
            return "function"
        if type_str in self.class_map:
            return "constructor"
        if "." in type_str and type_str.rsplit(".", 1)[0] in self.class_map:
            return "method"
        raise ValueError(
            f"Unknown node type '{type_str}': not a loaded primitive, function, class, or method"
        )

    def execute(self):
        """Execute the workflow"""
        order = self.get_execution_order()
        print(f"Execution order: {order}\n")

        for node_id in order:
            node = self.nodes[node_id]
            node_type = self._classify(node["type"])

            if node_type == "primitive":
                # Elementary nodes just return their value with type conversion
                raw_value = node["value"]
                prim_type = node.get("type", "any")

                # Convert value based on type using primitives_map
                if prim_type in self.primitives_map:
                    converter = self.primitives_map[prim_type]
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
                func_name = node["type"]
                func = self.function_map[func_name]

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
                    result = self.results[source_node_id]

                    # Handle source_output for tuple returns
                    if "source_output" in edge:
                        source_output_idx = edge["source_output"]
                        if isinstance(result, tuple) and source_output_idx < len(result):
                            result = result[source_output_idx]
                        # If source_output is 0 and result is not a tuple, use the result as-is
                        # (backwards compatible with single-output functions)

                    inputs.append(result)

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
                class_name = node["type"]
                cls = self.class_map[class_name]

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
                    result = self.results[source_node_id]

                    # Handle source_output for tuple returns
                    if "source_output" in edge:
                        source_output_idx = edge["source_output"]
                        if isinstance(result, tuple) and source_output_idx < len(result):
                            result = result[source_output_idx]

                    inputs.append(result)

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
                # Parse fully qualified name: "ClassName.method_name"
                fully_qualified_name = node["type"]
                class_name, method_name = fully_qualified_name.rsplit(".", 1)

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
                    result = self.results[source_node_id]

                    # Handle source_output for tuple returns
                    if "source_output" in edge:
                        source_output_idx = edge["source_output"]
                        if isinstance(result, tuple) and source_output_idx < len(result):
                            result = result[source_output_idx]

                    inputs.append(result)

                # Extract instance and method parameters
                instance = inputs[0]
                method_inputs = inputs[1:]

                # Verify instance is of correct class
                if not isinstance(instance, self.class_map[class_name]):
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
