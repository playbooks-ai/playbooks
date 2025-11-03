"""Agent proxy classes for intercepting and routing method calls in LLM-generated code.

This module provides the AIAgentProxy class and factory function to handle
cross-agent playbook calls (e.g., FileSystemAgent.validate_directory()) in
LLM-generated Python code. It uses the same "." in name routing logic as
execute_playbook to find and execute playbooks on other agents.

It also supports targeting specific agent instances using indexing syntax:
    AccountantExpert["agent 1020"].TaxRateQuery($gross_income)
"""

from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from playbooks.agents import AIAgent
    from playbooks.python_executor import LLMNamespace


def create_playbook_wrapper(
    playbook_name: str,
    current_agent: "AIAgent",
    namespace: "LLMNamespace",
    target_agent_id: Optional[str] = None,
) -> Callable[..., Any]:
    """Create a wrapper function for executing a playbook.

    Args:
        playbook_name: Name of the playbook to execute
        current_agent: The agent that will execute the playbook
        namespace: The namespace context for execution
        target_agent_id: Optional specific agent instance ID to target

    Returns:
        An async callable that executes the playbook and returns the result
    """

    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        # If targeting a specific agent instance, use AgentName:AgentId.PlaybookName format
        if target_agent_id:
            playbook_name_with_id = playbook_name.replace(
                ".", f":{target_agent_id}.", 1
            )
            success, result = await current_agent.execute_playbook(
                playbook_name_with_id, args, kwargs
            )
        else:
            success, result = await current_agent.execute_playbook(
                playbook_name, args, kwargs
            )
        if not success:
            return "ERROR: " + result
        return result

    return wrapper


class AIAgentInstanceProxy:
    """Proxy for a specific AI agent instance.

    This proxy is created when indexing an AIAgentProxy with an agent ID:
        AccountantExpert["agent 1020"]

    It routes playbook calls to the specific agent instance.
    """

    def __init__(
        self,
        proxied_agent_klass_name: str,
        target_agent_id: str,
        proxied_agent_klass: Any,
        current_agent: "AIAgent",
        namespace: "LLMNamespace",
    ) -> None:
        """Initialize the agent instance proxy.

        Args:
            proxied_agent_klass_name: The class name of the agent (e.g., "AccountantExpert")
            target_agent_id: The specific agent instance ID to target (e.g., "agent 1020")
            proxied_agent_klass: The agent class definition
            current_agent: The current agent executing the code
            namespace: The namespace context for execution
        """
        self._proxied_agent_klass_name = proxied_agent_klass_name
        self._target_agent_id = target_agent_id
        self._proxied_agent_klass = proxied_agent_klass
        self._current_agent = current_agent
        self._namespace = namespace

    def __getattr__(self, method_name: str) -> Callable[..., Any]:
        """Intercept method calls and route them to the specific agent instance.

        Args:
            method_name: The method name (playbook name)

        Returns:
            A callable that will execute the playbook on the specific agent instance

        Raises:
            AttributeError: If the method name starts with '_' (private) or playbook doesn't exist
        """
        # Prevent access to private attributes
        if method_name.startswith("_"):
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{method_name}'"
            )

        if method_name in self._proxied_agent_klass.playbooks:
            return create_playbook_wrapper(
                playbook_name=f"{self._proxied_agent_klass_name}.{method_name}",
                current_agent=self._current_agent,
                namespace=self._namespace,
                target_agent_id=self._target_agent_id,
            )
        else:
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{method_name}'"
            )

    def _is_coroutine_marker(self) -> bool:
        """Mark that proxy methods return coroutines.

        Returns:
            False (methods return coroutines, not the marker itself)
        """
        return False

    def __repr__(self) -> str:
        """Return a string representation of the proxy."""
        return f"AIAgentInstanceProxy({self._proxied_agent_klass_name}[{self._target_agent_id!r}])"


class AIAgentProxy:
    """Proxy for an AI agent that intercepts method calls and routes them to playbooks.

    When a method is called on this proxy (e.g., proxy.validate_directory()),
    it routes the call to the agent's execute_playbook method with the format
    "AgentName.method_name", which matches the cross-agent call pattern.

    Supports indexing to target specific agent instances:
        AccountantExpert.TaxRateQuery(...)  # Routes to first instance
        AccountantExpert["agent 1020"].TaxRateQuery(...)  # Routes to specific instance

    This proxy is designed to be used in the namespace when executing
    LLM-generated Python code.
    """

    def __init__(
        self,
        proxied_agent_klass_name: str,
        current_agent: "AIAgent",
        namespace: "LLMNamespace",
    ) -> None:
        """Initialize the agent proxy.

        Args:
            proxied_agent_klass_name: The class name of the agent (e.g., "FileSystemAgent")
            current_agent: The current agent executing the code (needed to access the program)
            namespace: The namespace context for execution
        """
        self._proxied_agent_klass_name = proxied_agent_klass_name
        self._proxied_agent_klass = current_agent.program.agent_klasses[
            proxied_agent_klass_name
        ]
        self._current_agent = current_agent
        self._namespace = namespace

    def __getitem__(self, agent_id: str) -> AIAgentInstanceProxy:
        """Support indexing to target a specific agent instance.

        Args:
            agent_id: The agent instance ID to target

        Returns:
            An AIAgentInstanceProxy targeting the specific agent instance
        """
        return AIAgentInstanceProxy(
            proxied_agent_klass_name=self._proxied_agent_klass_name,
            target_agent_id=agent_id,
            proxied_agent_klass=self._proxied_agent_klass,
            current_agent=self._current_agent,
            namespace=self._namespace,
        )

    def __getattr__(self, method_name: str) -> Callable[..., Any]:
        """Intercept method calls and route them through execute_playbook.

        Args:
            method_name: The method name (playbook name)

        Returns:
            A callable that will execute the playbook on the target agent

        Raises:
            AttributeError: If the method name starts with '_' (private) or playbook doesn't exist
        """
        # Prevent access to private attributes
        if method_name.startswith("_"):
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{method_name}'"
            )

        if method_name in self._proxied_agent_klass.playbooks:
            return create_playbook_wrapper(
                playbook_name=f"{self._proxied_agent_klass_name}.{method_name}",
                current_agent=self._current_agent,
                namespace=self._namespace,
            )
        else:
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{method_name}'"
            )

    def _is_coroutine_marker(self) -> bool:
        """Mark that proxy methods return coroutines.

        This helps the executor identify async functions in the namespace.

        Returns:
            False (methods return coroutines, not the marker itself)
        """
        return False

    def __repr__(self) -> str:
        """Return a string representation of the proxy."""
        return f"AIAgentProxy({self._proxied_agent_klass_name})"


def create_agent_proxies(
    current_agent: "AIAgent", namespace: "LLMNamespace"
) -> dict[str, AIAgentProxy]:
    """Create agent proxy objects for all agents in the program.

    Creates proxies for all agents except the current agent, enabling
    cross-agent playbook calls from LLM-generated code.

    Args:
        current_agent: The current agent executing the code
        namespace: The namespace context for execution

    Returns:
        Dictionary mapping agent class names to AIAgentProxy instances
    """
    proxies = {}

    if current_agent.program and hasattr(current_agent.program, "agents"):
        for proxied_agent_klass_name in current_agent.program.agent_klasses:
            # Skip creating a proxy for the current agent itself
            if proxied_agent_klass_name != current_agent.klass:
                proxies[proxied_agent_klass_name] = AIAgentProxy(
                    proxied_agent_klass_name=proxied_agent_klass_name,
                    current_agent=current_agent,
                    namespace=namespace,
                )

    return proxies
