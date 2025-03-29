from .base_agent import BaseAgent
from .config import LLMConfig
from .enums import RoutingType


class MessageRouter:
    """
    Routes messages between agents in the playbook system.

    Provides utility methods for agent communication.
    """

    @staticmethod
    def send_message(
        message: str,
        from_agent: BaseAgent,
        to_agent: BaseAgent,
        llm_config: LLMConfig,
        stream: bool = False,
    ):
        """
        Send a message from one agent to another and yield response chunks.

        Args:
            message: The message content.
            from_agent: The sender agent.
            to_agent: The recipient agent.
            llm_config: LLM configuration.
            stream: Whether to stream responses (default: False).

        Yields:
            Response chunks from the recipient agent.
        """
        routing_type = RoutingType.DIRECT

        # Forward to recipient's process_message method
        yield from to_agent.process_message(
            message=message,
            from_agent=from_agent,
            routing_type=routing_type,
            llm_config=llm_config,
            stream=stream,
        )
