"""Raw LLM call execution without loops or structure."""

from typing import TYPE_CHECKING, Any, List

from ..enums import LLMMessageRole, LLMMessageType
from ..events import PlaybookEndEvent, PlaybookStartEvent
from ..playbook_call import PlaybookCall
from ..utils.expression_engine import (
    ExpressionContext,
)
from ..utils.llm_config import LLMConfig
from ..utils.llm_helper import get_completion, make_uncached_llm_message
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

    async def execute(self, *args, **kwargs) -> Any:
        """Execute with a raw LLM call."""
        # Note: Call stack management is handled by the agent's execute_playbook method
        # No need to push/pop here as it would create double management

        # Publish playbook start event
        self.state.event_bus.publish(PlaybookStartEvent(playbook=self.playbook.name))

        # Build the prompt
        messages = await self._build_prompt(*args, **kwargs)

        # Make single LLM call
        response = await self._get_llm_response(messages)

        # Parse and return the response
        result = self._parse_response(response)

        # Publish playbook end event
        call_stack_depth = len(self.state.call_stack.frames)
        self.state.event_bus.publish(
            PlaybookEndEvent(
                playbook=self.playbook.name,
                return_value=result,
                call_stack_depth=call_stack_depth,
            )
        )

        return result

    async def _build_prompt(self, *args, **kwargs) -> str:
        call = PlaybookCall(self.playbook.name, args, kwargs)

        context = ExpressionContext(self, self.state, call)
        resolved_description = await context.resolve_description_placeholders(
            self.description, context
        )

        stack_frame = self.agent.state.call_stack.peek()
        messages = list(
            filter(
                lambda message: message["type"] == LLMMessageType.LOAD_FILE,
                stack_frame.llm_messages,
            )
        )
        messages.append(
            make_uncached_llm_message(
                resolved_description,
                role=LLMMessageRole.ASSISTANT,
                type=LLMMessageType.DEFAULT,
            )
        )
        return messages

    async def _get_llm_response(self, messages: List[dict]) -> str:
        """Get response from LLM."""
        # Get completion
        response_generator = get_completion(
            messages=messages,
            llm_config=LLMConfig(),
            stream=False,
            json_mode=False,
            langfuse_span=self.state.call_stack.peek().langfuse_span,
        )

        response = next(response_generator)

        # Cache the response
        self.state.call_stack.peek().add_cached_llm_message(
            response, role=LLMMessageRole.ASSISTANT
        )

        return response

    def _parse_response(self, response: str) -> Any:
        """Parse the LLM response.

        For raw mode, we return the response as-is.
        In the future, this could be enhanced to parse structured outputs.
        """
        return response.strip()
