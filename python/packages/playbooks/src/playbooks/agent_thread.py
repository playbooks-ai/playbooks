from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .agent import Agent

from .interpreter import Interpreter


class AgentThread:
    def __init__(self, agent: "Agent"):
        self.agent = agent
        self.interpreter = Interpreter()
        self.history: List[Dict[str, Any]] = []

    def get_context_history(self, max_items: int = 10) -> str:
        """Get a compacted form of history for context.

        Args:
            max_items: Maximum number of history items to include

        Returns:
            A string containing the compacted history
        """
        if not self.history:
            return ""

        recent_history = self.history[-max_items:]
        context = []
        for item in recent_history:
            msg_from = item["from_agent"].klass if item["from_agent"] else "system"
            context.append(
                f"Received {item['routing_type']} message from {msg_from}: {item['message']}\n"
            )
            context.append(item["response"])
            context.append("\n")
            context.append("-" * 20)
            context.append("\n")

        return "\n".join(context)

    def process_message(
        self,
        message: str,
        from_agent: Optional["Agent"],
        routing_type: str,
        llm_config: dict = None,
        stream: bool = False,
    ):
        instruction = f"Received {routing_type} message from {from_agent.klass if from_agent is not None else 'system'}: {message}"

        # Add context from history if available
        context = self.get_context_history()
        if context:
            instruction = f"**Previous context** -\n{context}\n\n**Current context** -\n{instruction}"

        response_chunks = []
        for chunk in self.interpreter.run(
            included_playbooks=self.agent.playbooks,
            instruction=instruction,
            llm_config=llm_config,
            stream=stream,
        ):
            response_chunks.append(chunk)
            yield chunk

        # Store in history
        self.history.append(
            {
                "message": message,
                "from_agent": from_agent,
                "routing_type": routing_type,
                "response": "".join(response_chunks),
            }
        )
