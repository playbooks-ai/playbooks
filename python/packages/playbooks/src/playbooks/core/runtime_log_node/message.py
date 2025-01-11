"""Message runtime log node."""

from typing import Optional

from playbooks.enums import AgentType, RoutingType

from .base import RuntimeLogNode


class MessageRuntimeLogNode(RuntimeLogNode):
    """A log node for messages."""

    @classmethod
    def create(
        cls,
        message: str,
        role: str = "agent",
        message_id: Optional[str] = None,
        from_agent_id: Optional[str] = None,
        from_agent_klass: Optional[str] = None,
        from_agent_type: Optional[AgentType] = None,
        to_agent_id: Optional[str] = None,
        to_agent_klass: Optional[str] = None,
        to_agent_type: Optional[AgentType] = None,
        parent_log_node_id: Optional[int] = None,
        routing_type: Optional[RoutingType] = None,
    ) -> "MessageRuntimeLogNode":
        instance = cls(
            parent_log_node_id=parent_log_node_id,
            type="message",
            info={
                "id": message_id,
                "role": role,
                "from_agent_id": from_agent_id,
                "from_agent_klass": from_agent_klass,
                "from_agent_type": from_agent_type,
                "to_agent_id": to_agent_id,
                "to_agent_klass": to_agent_klass,
                "to_agent_type": to_agent_type,
                "message": message,
                "routing_type": routing_type,
            },
        )
        return instance
