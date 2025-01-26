from typing import Any, Optional

from .agent_thread import AgentThread
from .base_agent import BaseAgent
from .exceptions import (
    AgentAlreadyRunningError,
    AgentConfigurationError,
)
from .playbook import Playbook


class Agent(BaseAgent):
    """
    Base class for AI agents.
    """

    def __init__(self, klass: str, description: str, playbooks: list[Playbook] = []):
        self.klass = klass
        self.description = description
        self.playbooks: list[Playbook] = playbooks
        self.main_thread: Optional[Any] = None
        self.run()

    def run(self, llm_config: dict = None, stream: bool = False):
        """Run the agent."""
        # raise custom exception AgentConfigurationError if no playbooks are defined
        if len(self.playbooks) == 0:
            raise AgentConfigurationError("No playbooks defined for AI agent")

        # raise custom exception AgentAlreadyRunningError if agent is already running
        if self.main_thread is not None:
            raise AgentAlreadyRunningError("AI agent is already running")

        # create self.main_thread of type AgentThread
        self.main_thread = AgentThread(self)

        # run the main thread
        # TODO: add support for filtering playbooks
        for chunk in self.main_thread.run(
            included_playbooks=self.playbooks,
            instruction="Begin",
            llm_config=llm_config,
            stream=stream,
        ):
            yield chunk

    def process_message(
        self,
        message: str,
        from_agent: "Agent",
        routing_type: str,
        llm_config: dict = None,
        stream: bool = False,
    ):
        # Process the message on main thread
        for chunk in self.main_thread.run(
            included_playbooks=self.playbooks,
            instruction=f"Received the following message from {from_agent.klass}: {message}",
            llm_config=llm_config,
            stream=stream,
        ):
            yield chunk
