"""Agent proxy classes for intercepting and routing method calls in LLM-generated code.

This module provides the AIAgentProxy class and factory function to handle
cross-agent playbook calls (e.g., FileSystemAgent.validate_directory()) in
LLM-generated Python code. It uses the same "." in name routing logic as
execute_playbook to find and execute playbooks on other agents.
"""

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from playbooks.agents import AIAgent
    from playbooks.python_executor import LLMNamespace


def create_playbook_wrapper(
    playbook_name: str, current_agent: "AIAgent", namespace: "LLMNamespace"
) -> Callable:
    async def wrapper(*args, **kwargs):
        await current_agent.execute_playbook(playbook_name, args, kwargs)

    return wrapper


class AIAgentProxy:
    """Proxy for an AI agent that intercepts method calls and routes them to playbooks.

    When a method is called on this proxy (e.g., proxy.validate_directory()),
    it routes the call to the agent's execute_playbook method with the format
    "AgentName.method_name", which matches the cross-agent call pattern.

    This proxy is designed to be used in the namespace when executing
    LLM-generated Python code.
    """

    def __init__(
        self,
        proxied_agent_klass_name: str,
        current_agent: "AIAgent",
        namespace: "LLMNamespace",
    ):
        """Initialize the agent proxy.

        Args:
            proxied_agent_klass_name: The class name of the agent (e.g., "FileSystemAgent")
            current_agent: The current agent executing the code (needed to access the program)
        """
        self._proxied_agent_klass_name = proxied_agent_klass_name
        self._proxied_agent_klass = current_agent.program.agent_klasses[
            proxied_agent_klass_name
        ]
        self._current_agent = current_agent
        self._namespace = namespace

    def __getattr__(self, method_name: str) -> Callable:
        """Intercept method calls and route them through execute_playbook.

        Args:
            method_name: The method name (playbook name)

        Returns:
            A callable that will execute the playbook on the target agent

        Raises:
            AttributeError: If the method name starts with '_' (private)
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
        return False

    def __repr__(self) -> str:
        """Return a string representation of the proxy."""
        return f"AIAgentProxy({self._proxied_agent_klass_name})"


def create_agent_proxies(
    current_agent: "AIAgent", namespace: "LLMNamespace"
) -> dict[str, AIAgentProxy]:
    """Create agent proxy objects for all agents in the program.

    Args:
        current_agent: The current agent executing the code

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
