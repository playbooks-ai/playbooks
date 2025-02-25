from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .agent import Agent

from .interpreter import Interpreter
from .trace_mixin import TraceMixin
from .types import AgentResponseChunk, ToolResponse

if TYPE_CHECKING:
    from .agent import BaseAgent


class MessageReceived(TraceMixin):
    def __init__(self, message: str, from_agent: "BaseAgent"):
        super().__init__()
        self.message = message
        self.from_agent = from_agent or "System"

    def __repr__(self):
        return f"{self.from_agent}: {self.message}"


class AgentThread:
    def __init__(self, agent: "Agent"):
        self.agent = agent
        self.interpreter = Interpreter()

    def process_message(
        self,
        message: str,
        from_agent: Optional["Agent"],
        routing_type: str,
        llm_config: dict = None,
        stream: bool = False,
    ):
        instruction = f"Received {routing_type} message from {from_agent.klass if from_agent is not None else 'system'}: {message}"

        self.interpreter.trace(MessageReceived(message, from_agent))

        chunks = []
        for chunk in self.interpreter.execute(
            playbooks=self.agent.playbooks,
            instruction=instruction,
            llm_config=llm_config,
            stream=stream,
        ):
            chunks.append(chunk)
            yield chunk

        tool_calls = [chunk.tool_call for chunk in chunks if chunk.tool_call]

        # Execute tools
        instruction = []
        if tool_calls:
            instructions = []
            for tool_call in tool_calls:
                if tool_call.fn == "Say":
                    yield AgentResponseChunk(agent_response=tool_call.args[0] + "\n")
                else:
                    tool_retval = tool_call.retval
                    if tool_retval:
                        tool_call_message = f"{tool_call.fn}() returned {tool_retval}"
                        instructions.append(tool_call_message)
                        yield AgentResponseChunk(
                            tool_response=ToolResponse(tool_call.fn, tool_retval)
                        )

            instruction = "\n".join(instructions)
