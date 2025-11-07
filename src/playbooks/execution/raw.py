"""Raw LLM call execution without loops or structure."""

from typing import TYPE_CHECKING, Any, Dict, List

from playbooks.core.enums import LLMMessageType
from playbooks.core.events import PlaybookEndEvent, PlaybookStartEvent
from playbooks.llm.messages import AssistantResponseLLMMessage, UserInputLLMMessage
from playbooks.execution.call import PlaybookCall
from playbooks.compilation.expression_engine import (
    ExpressionContext,
    resolve_description_placeholders,
)
from playbooks.utils.llm_config import LLMConfig
from playbooks.utils.llm_helper import get_completion
from .base import LLMExecution

if TYPE_CHECKING:
    pass


class RawLLMExecution(LLMExecution):
    """Raw LLM call execution without loops or structure.

    This mode:
    - Makes ONE LLM call
    - No loops or iterations
    - No structured steps
    - Direct prompt → response
    """

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute with a raw LLM call.

        Makes a single LLM call without loops or structured steps.
        Publishes playbook start/end events for observability.

        Args:
            *args: Positional arguments for the playbook
            **kwargs: Keyword arguments for the playbook

        Returns:
            Parsed response from the LLM
        """
        # Note: Call stack management is handled by the agent's execute_playbook method
        # No need to push/pop here as it would create double management

        # Publish playbook start event
        self.agent.state.event_bus.publish(
            PlaybookStartEvent(
                agent_id=self.agent.id, session_id="", playbook=self.playbook.name
            )
        )

        # Build the prompt
        messages = await self._build_prompt(*args, **kwargs)

        # Make single LLM call
        response = await self._get_llm_response(messages)

        # Parse and return the response
        result = self._parse_response(response)

        # Publish playbook end event
        call_stack_depth = len(self.agent.state.call_stack.frames)
        self.agent.state.event_bus.publish(
            PlaybookEndEvent(
                agent_id=self.agent.id,
                session_id="",
                playbook=self.playbook.name,
                return_value=result,
                call_stack_depth=call_stack_depth,
            )
        )

        return result

    async def _build_prompt(self, *args: Any, **kwargs: Any) -> List[Dict[str, str]]:
        """Build the prompt for raw LLM execution.

        Resolves description placeholders and includes file load messages
        from the call stack.

        Args:
            *args: Positional arguments for the playbook
            **kwargs: Keyword arguments for the playbook

        Returns:
            List of message dictionaries for LLM API
        """
        call = PlaybookCall(self.playbook.name, args, kwargs)

        context = ExpressionContext(agent=self.agent, state=self.agent.state, call=call)
        resolved_description = await resolve_description_placeholders(
            self.playbook.description, context
        )

        stack_frame = self.agent.state.call_stack.peek()
        # Get file load messages from the call stack
        messages = [
            msg.to_full_message()
            for msg in stack_frame.llm_messages
            if msg.type == LLMMessageType.FILE_LOAD
        ]
        messages.append(UserInputLLMMessage(resolved_description).to_full_message())
        return messages

    async def _get_llm_response(self, messages: List[Dict[str, str]]) -> str:
        """Get response from LLM.

        Makes a single completion call and caches the response in the call stack.

        Args:
            messages: List of message dictionaries for LLM API

        Returns:
            Response string from the LLM
        """
        # Get completion
        response_generator = get_completion(
            messages=messages,
            llm_config=LLMConfig(),
            stream=False,
            json_mode=False,
            langfuse_span=self.agent.state.call_stack.peek().langfuse_span,
        )

        response = next(response_generator)

        # Cache the response
        response_msg = AssistantResponseLLMMessage(response)  # cached=True by default
        self.agent.state.call_stack.add_llm_message(response_msg)

        return response

    def _parse_response(self, response: str) -> Any:
        """Parse the LLM response.

        For raw mode, we return the response as-is (stripped of whitespace).
        In the future, this could be enhanced to parse structured outputs.

        Args:
            response: Raw response string from LLM

        Returns:
            Parsed response (currently just stripped string)
        """
        return response.strip()
