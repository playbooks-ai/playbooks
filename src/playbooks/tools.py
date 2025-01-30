import ast
import typing

if typing.TYPE_CHECKING:
    from .agent_thread import AgentThread
    from .types import ToolCall


class Tools:
    def __init__(self):
        self._tools = {}

    def add_tools(self, code: str):
        # Parse python code using ast
        tree = ast.parse(code)

        # Get the module's globals
        module_globals = {}

        # Find all function definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Create function object from AST node
                code_obj = compile(
                    ast.Module(body=[node], type_ignores=[]),
                    filename="<ast>",
                    mode="exec",
                )

                # Execute the code object to create the function
                exec(code_obj, module_globals)

                # Get the function from globals
                func = module_globals[node.name]

                # Add the function to tools dictionary
                self._tools[node.name] = func

    def __call__(self, tool_call: "ToolCall", agent_thread: "AgentThread"):
        # Perform the tool call
        tool = self._tools[tool_call.fn]
        retval = tool(*tool_call.args, **tool_call.kwargs)
        return retval
