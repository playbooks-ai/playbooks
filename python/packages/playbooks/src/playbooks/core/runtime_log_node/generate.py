from typing import Optional

from playbooks.enums import AgentType

from .base import RuntimeLogNode


class GenerateRuntimeLogNode(RuntimeLogNode):
    """Log entry indicating agent generated content."""

    @classmethod
    def create(
        cls,
        generated_content: str,
        from_agent_id: Optional[str] = None,
        from_agent_klass: Optional[str] = None,
        from_agent_type: Optional[AgentType] = None,
        parent_log_node_id: Optional[int] = None,
    ) -> "GenerateRuntimeLogNode":
        instance = cls(
            parent_log_node_id=parent_log_node_id,
            type="generate",
            info={
                "from_agent_id": from_agent_id,
                "from_agent_klass": from_agent_klass,
                "from_agent_type": from_agent_type,
                "generated_content": generated_content,
            },
        )
        return instance
