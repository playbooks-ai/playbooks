import ast
import asyncio
import inspect
from typing import Any, Dict, Set


class AutoAsyncCalls:
    """
    Automatically transforms synchronous function calls to async/await calls
    based on the namespace provided.
    """

    def __init__(self):
        self.async_functions = set()
        self.async_methods = set()

    def run(self, code: str, namespace: Dict[str, Any]) -> str:
        """
        Transform code to add await for async function calls and wrap in async function.

        Args:
            code: Python code as string
            namespace: Dictionary of available functions/objects

        Returns:
            Transformed code wrapped in an async function
        """
        # Detect async functions and methods from namespace
        self._detect_async_callables(namespace)

        # Parse the code into AST
        tree = ast.parse(code)

        # Transform the AST to add awaits
        transformer = self._AsyncTransformer(
            self.async_functions, self.async_methods, namespace
        )
        new_tree = transformer.visit(tree)

        # Fix missing locations for new nodes
        ast.fix_missing_locations(new_tree)

        # Convert back to code
        transformed_code = ast.unparse(new_tree)

        # Wrap in async function
        wrapped_code = self._wrap_in_async_function(transformed_code)

        # Ensure asyncio is in namespace for execution
        dict.__setitem__(namespace, "asyncio", asyncio)

        return wrapped_code

    def _wrap_in_async_function(self, code: str) -> str:
        """Wrap code in an async function definition"""
        # Indent the code
        indented_lines = [f"    {line}" for line in code.splitlines()]
        indented_code = "\n".join(indented_lines)

        # Just define the async function, don't try to call asyncio.run at module level
        # The executor will handle awaiting this coroutine
        wrapped = f"""async def __async_exec__():
{indented_code}
"""
        return wrapped

    def _detect_async_callables(self, namespace: Dict[str, Any]):
        """Detect async functions and methods in the namespace"""
        self.async_functions = set()
        self.async_methods = set()

        for name, obj in namespace.items():
            # Check if it's an async function
            if inspect.iscoroutinefunction(obj):
                self.async_functions.add(name)

            # Check if it's a class with async methods
            elif inspect.isclass(obj):
                for method_name, method in inspect.getmembers(obj, inspect.isfunction):
                    if inspect.iscoroutinefunction(method):
                        self.async_methods.add(method_name)

            # Check if it's an instance with async methods
            elif hasattr(obj, "__class__"):
                for method_name in dir(obj):
                    if not method_name.startswith("_"):
                        try:
                            method = getattr(obj, method_name)
                            if inspect.iscoroutinefunction(method):
                                self.async_methods.add(method_name)
                        except Exception:
                            pass

    class _AsyncTransformer(ast.NodeTransformer):
        """AST transformer to add await to async calls"""

        def __init__(
            self,
            async_functions: Set[str],
            async_methods: Set[str],
            namespace: Dict[str, Any],
        ):
            self.async_functions = async_functions
            self.async_methods = async_methods
            self.namespace = namespace

        def visit_Call(self, node):
            # First, recursively transform child nodes
            self.generic_visit(node)

            should_await = False

            # Handle direct function calls: func()
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                if func_name in self.async_functions:
                    should_await = True

            # Handle method calls: obj.method() or Class.method()
            elif isinstance(node.func, ast.Attribute):
                method_name = node.func.attr

                # Try to determine if this method is async
                # First check our pre-detected async methods
                if method_name in self.async_methods:
                    should_await = True
                else:
                    # Try to look up the object and check the method directly
                    should_await = self._is_method_async(node.func)

            if should_await:
                return ast.Await(value=node)

            return node

        def _is_method_async(self, attribute_node):
            """
            Try to determine if a method call is async by looking up the object.
            If unable to determine, default to True (await it).
            """
            method_name = attribute_node.attr

            # Try to get the object being called on
            obj_node = attribute_node.value

            # If it's a simple name like FileSystemAgent.validate_directory
            if isinstance(obj_node, ast.Name):
                obj_name = obj_node.id

                # Check if the object is in our namespace
                if obj_name in self.namespace:
                    obj = self.namespace[obj_name]

                    # Try to get the method
                    try:
                        if hasattr(obj, method_name):
                            method = getattr(obj, method_name)
                            # Check if it's async
                            if inspect.iscoroutinefunction(method):
                                return True
                            else:
                                return False
                    except Exception:
                        pass

                # Object not in namespace or couldn't determine - default to await
                return True

            # For more complex expressions (chained calls, etc.), default to await
            return True


def await_async_calls(code: str, namespace: Dict[str, Any]) -> str:
    """
    Transform code to add await for async function calls and wrap in async function.
    """
    transformer = AutoAsyncCalls()
    return transformer.run(code, namespace)
