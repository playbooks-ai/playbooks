"""Python function-based playbooks.

This module provides playbooks that wrap Python functions decorated with
@playbook, enabling direct execution of Python code as agent actions.
"""

import inspect
from typing import Any, Callable, Dict, Optional

from .local import LocalPlaybook


class PythonPlaybook(LocalPlaybook):
    """Represents a Python playbook created from @playbook decorated functions.

    Python playbooks are defined using the @playbook decorator and contain
    executable Python code.
    """

    @classmethod
    def create_playbooks_from_h1(
        cls, h1: Dict, namespace_manager
    ) -> Dict[str, "PythonPlaybook"]:
        """Create PythonPlaybook instances from H1 AST node.

        Args:
            h1: H1 AST node containing agent definition
            namespace_manager: Namespace manager for executing code blocks

        Returns:
            Dict[str, PythonPlaybook]: Dictionary of created playbooks
        """
        playbooks = {}

        for child in h1.get("children", []):
            if child.get("type") == "code-block" and child.get("language") == "python":
                new_playbooks = cls.create_playbooks_from_code_block(
                    child["text"],
                    namespace_manager,
                    child.get("source_file_path"),
                    child.get("line_number"),
                )
                playbooks.update(new_playbooks)

        return playbooks

    @classmethod
    def create_playbooks_from_code_block(
        cls,
        code_block: str,
        namespace_manager,
        source_file_path: Optional[str] = None,
        source_line_number: Optional[int] = None,
    ) -> Dict[str, "PythonPlaybook"]:
        """Create PythonPlaybook instances from a code block.

        Args:
            code_block: Python code containing @playbook decorated functions
            namespace_manager: Namespace manager for execution environment

        Returns:
            Dict[str, PythonPlaybook]: Dictionary of discovered playbooks
        """
        import ast

        # Set up the execution environment
        existing_keys = list(namespace_manager.namespace.keys())
        environment = namespace_manager.prepare_execution_environment()
        namespace_manager.namespace.update(environment)

        # Execute the code block in the isolated namespace
        python_local_namespace = {}
        exec(code_block, namespace_manager.namespace, python_local_namespace)
        namespace_manager.namespace.update(python_local_namespace)

        # Get code for each function
        function_code = {}
        items = {}
        parsed_code = ast.parse(code_block)
        # debug("Parsed Code: " + str(parsed_code))
        for item in parsed_code.body:
            if isinstance(item, ast.AsyncFunctionDef) or isinstance(
                item, ast.FunctionDef
            ):
                function_code[item.name] = ast.unparse(item)
                items[item.name] = item

        # Discover all @playbook-decorated functions
        playbooks = cls._discover_playbook_functions(namespace_manager, existing_keys)
        # debug("decorated functions: " + str(playbooks))
        # Add function code to playbooks
        for playbook in playbooks.values():
            playbook.code = function_code[playbook.name]
            playbook.source_file_path = source_file_path

            line_offset = 0
            if items[playbook.name].lineno is not None:
                line_offset = items[playbook.name].lineno
            playbook.source_line_number = source_line_number + line_offset

        return playbooks

    @classmethod
    def _discover_playbook_functions(
        cls, namespace_manager, existing_keys
    ) -> Dict[str, "PythonPlaybook"]:
        """Discover playbook-decorated functions in the namespace.

        Args:
            namespace_manager: Namespace manager containing executed code
            existing_keys: Keys that existed before code execution

        Returns:
            Dict[str, PythonPlaybook]: Discovered playbooks
        """
        import types

        playbooks = {}
        wrappers = {}

        for obj_name, obj in namespace_manager.namespace.items():
            if (
                isinstance(obj, types.FunctionType)
                and obj_name not in existing_keys
                and getattr(obj, "__is_playbook__", False)
            ):
                # Create playbook from decorated function
                playbooks[obj.__name__] = cls.from_function(obj)

                # Only create namespace functions if agent is available
                agent = namespace_manager.namespace.get("agent")
                if agent is not None:
                    wrappers[obj.__name__] = playbooks[
                        obj.__name__
                    ].create_namespace_function(agent)

        namespace_manager.namespace.update(wrappers)
        return playbooks

    @classmethod
    def from_function(cls, func: "Callable") -> "PythonPlaybook":
        """Create a PythonPlaybook object from a decorated function.

        Args:
            func: Decorated function

        Returns:
            PythonPlaybook: Created playbook object
        """
        import inspect
        import re

        from playbooks.triggers import PlaybookTriggers

        sig = inspect.signature(func)
        signature = func.__name__ + str(sig)
        doc = inspect.getdoc(func)
        description = doc.split("\n")[0] if doc is not None else None
        triggers = getattr(func, "__triggers__", [])
        metadata = getattr(func, "__metadata__", {})

        # If triggers are not prefixed with T1:BGN, T1:CND, etc., add appropriate prefix
        # Use regex to find if prefix is missing
        for i, trigger in enumerate(triggers):
            if not re.match(r"^T\d+:[A-Z]{3} ", trigger):
                raise ValueError(
                    f"Expected trigger {trigger} to be prefixed with T1:BGN, T1:CND, etc."
                )

        if triggers:
            triggers = PlaybookTriggers(
                playbook_klass=func.__name__,
                playbook_signature=signature,
                triggers=triggers,
            )
        else:
            triggers = None

        return cls(
            name=func.__name__,
            func=func,
            signature=signature,
            description=description,
            triggers=triggers,
            metadata=metadata,
        )

    def __init__(
        self,
        name: str,
        func: Callable,
        signature: str,
        description: Optional[str] = None,
        agent_name: Optional[str] = None,
        triggers: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        code: Optional[str] = None,
        source_file_path: Optional[str] = None,
        source_line_number: Optional[int] = None,
    ):
        """Initialize a PythonPlaybook.

        Args:
            name: The name of the playbook (function name)
            func: The decorated function to execute
            signature: The function signature string
            description: Human-readable description of the playbook
            agent_name: Name of the agent this playbook belongs to
            triggers: Trigger configuration for the playbook
            metadata: Additional metadata for the playbook
            code: The source code of the function
            source_file_path: The file path of the source where this playbook is defined
            source_line_number: The line number in the source where this playbook is defined
        """
        super().__init__(
            name=name,
            description=description,
            agent_name=agent_name,
            metadata=metadata,
            source_file_path=source_file_path,
            source_line_number=source_line_number,
        )

        self.func = func
        self.signature = signature
        self.triggers = triggers
        self.code = code
        # For backward compatibility with existing code
        self.klass = name

    async def _execute_impl(self, *args, **kwargs) -> Any:
        """Execute the Python playbook function.

        Args:
            *args: Positional arguments for the playbook
            **kwargs: Keyword arguments for the playbook

        Returns:
            The result of executing the function
        """
        if not self.func:
            raise ValueError(f"PythonPlaybook {self.name} has no executable function")

        # Execute the function (it may be sync or async)
        if inspect.iscoroutinefunction(self.func):
            return await self.func(*args, **kwargs)
        else:
            return self.func(*args, **kwargs)

    def get_parameters(self) -> Dict[str, Any]:
        """Get the parameters schema for this playbook.

        Returns:
            A dictionary describing the expected parameters based on the function signature
        """
        if not self.func:
            return {}

        sig = inspect.signature(self.func)
        parameters = {}

        for param_name, param in sig.parameters.items():
            param_info = {
                "name": param_name,
                "kind": param.kind.name,
            }

            if param.annotation != inspect.Parameter.empty:
                param_info["type"] = str(param.annotation)

            if param.default != inspect.Parameter.empty:
                param_info["default"] = param.default

            parameters[param_name] = param_info

        return {
            "signature": self.signature,
            "parameters": parameters,
            "description": f"Parameters for {self.name} Python playbook",
        }

    def get_description(self) -> str:
        """Get a human-readable description of this playbook.

        Returns:
            The description of the playbook
        """
        return self.description or self.name

    def __repr__(self) -> str:
        """Return a string representation of the playbook."""
        return f"PythonPlaybook(name='{self.name}', agent='{self.agent_name}')"
