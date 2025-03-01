from typing import Dict, Optional

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

    def __init__(
        self,
        klass: str,
        description: str,
        playbooks: Dict[str, Playbook] = {},
    ):
        self.klass = klass
        self.description = description
        self.playbooks = playbooks
        self.main_thread: Optional[AgentThread] = None
        self.run()

    def run(self, llm_config: dict = None, stream: bool = False):
        """Run the agent."""
        # raise custom exception AgentAlreadyRunningError if agent is already running
        if self.main_thread is not None:
            raise AgentAlreadyRunningError("AI agent is already running")

        # run the main thread
        # TODO: add support for filtering playbooks
        for chunk in self.process_message(
            message="Begin",
            from_agent=None,
            routing_type="direct",
            llm_config=llm_config,
            stream=stream,
        ):
            yield chunk

    def process_message(
        self,
        message: str,
        from_agent: Optional["Agent"],
        routing_type: str,
        llm_config: dict = None,
        stream: bool = False,
    ):
        # raise custom exception AgentConfigurationError if no playbooks are defined
        if len(self.playbooks) == 0:
            raise AgentConfigurationError("No playbooks defined for AI agent")

        # create self.main_thread of type AgentThread
        if self.main_thread is None:
            self.main_thread = AgentThread(self)

        # Process the message on main thread
        for chunk in self.main_thread.process_message(
            message=message,
            from_agent=from_agent,
            routing_type=routing_type,
            llm_config=llm_config,
            stream=stream,
        ):
            yield chunk

    def __repr__(self):
        return self.klass

    def __str__(self):
        return self.klass
