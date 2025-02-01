from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .agent import Agent

from .interpreter import Interpreter
from .types import AgentResponseChunk, ToolResponse


class AgentThread:
    def __init__(self, agent: "Agent"):
        self.agent = agent
        self.interpreter = Interpreter()
        self.history: List[Dict[str, Any]] = []

    def get_context_history(self, max_items: int = 20) -> str:
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
            if "from_agent" in item and item["from_agent"] is not None:
                msg_from = item["from_agent"].klass
            else:
                msg_from = "System"
            context.append(f"- {msg_from}: {item['message']}")

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

        # Store in history
        self.history.append(
            {
                "message": message,
                "from_agent": from_agent,
            }
        )

        waiting_for_user_input = False
        while not waiting_for_user_input:
            # TODO: Fix instruction and context history for looping on tool call

            # Add context from history if available
            session_context = self.get_context_history()
            if session_context:
                session_context = "Session log:\n" + session_context

            chunks = []
            for chunk in self.interpreter.run(
                included_playbooks=self.agent.playbooks,
                instruction=instruction,
                session_context=session_context,
                llm_config=llm_config,
                stream=stream,
            ):
                chunks.append(chunk)
                yield chunk

            tool_calls = [chunk.tool_call for chunk in chunks if chunk.tool_call]

            # Execute tools
            external_call_made = False
            instruction = []
            for tool_call in tool_calls:
                if tool_call.fn == "Say":
                    yield AgentResponseChunk(agent_response=tool_call.args[0])
                    self.history.append(
                        {
                            "message": tool_call.args[0],
                            "from_agent": self.agent,
                        }
                    )
                else:
                    retval = self.agent.execute_tool(tool_call)
                    external_call_made = True
                    tool_call_message = f"{tool_call.fn}() returned {retval}"
                    instruction.append(tool_call_message)
                    yield AgentResponseChunk(
                        tool_response=ToolResponse(tool_call.fn, retval)
                    )
                    self.history.append(
                        {
                            "message": tool_call_message,
                        }
                    )

            instruction = "\n".join(instruction)
            if self.interpreter.yield_requested_on_say or not external_call_made:
                waiting_for_user_input = True
