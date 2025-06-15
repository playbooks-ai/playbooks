import inspect
from typing import Any, Callable, Dict, Optional

from .local import LocalPlaybook


class PythonPlaybook(LocalPlaybook):
    """Represents a Python playbook created from @playbook decorated functions.

    Python playbooks are defined using the @playbook decorator and contain
    executable Python code.
    """

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
            source_line_number: The line number in the source where this playbook is defined
        """
        super().__init__(
            name=name,
            description=description,
            agent_name=agent_name,
            metadata=metadata,
        )

        self.func = func
        self.signature = signature
        self.triggers = triggers
        self.code = code
        self.source_line_number = source_line_number

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
