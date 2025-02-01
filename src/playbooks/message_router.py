from .base_agent import BaseAgent
from .config import LLMConfig
from .enums import RoutingType


class MessageRouter:
    def __init__(self):
        pass

    @staticmethod
    def send_message(
        message: str,
        from_agent: BaseAgent,
        to_agent: BaseAgent,
        llm_config: LLMConfig,
        stream=False,
    ):
        """Send a message from one agent to another."""
        routing_type = RoutingType.DIRECT

        # # Create a message log node to track the conversation
        # message_node = MessageRuntimeLogNode.create(
        #     message=message,
        #     from_agent_id=from_agent.id,
        #     from_agent_klass=from_agent.klass,
        #     from_agent_type=from_agent.type,
        #     to_agent_id=to_agent.id,
        #     to_agent_klass=to_agent.klass,
        #     to_agent_type=to_agent.type,
        #     routing_type=routing_type,
        # )

        # # Add the message to runtime's log
        # self.runtime.add_runtime_log(message_node)

        # Process the message using the recipient agent's process_message method
        for chunk in to_agent.process_message(
            message=message,
            from_agent=from_agent,
            routing_type=routing_type,
            llm_config=llm_config,
            stream=stream,
        ):
            yield chunk
