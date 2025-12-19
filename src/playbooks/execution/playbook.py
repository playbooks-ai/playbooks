"""Traditional playbook execution with defined steps."""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from playbooks.compilation.expression_engine import (
    ExpressionContext,
    bind_call_parameters,
    resolve_description_placeholders,
    update_description_in_markdown,
)
from playbooks.config import config
from playbooks.core.argument_types import LiteralValue, VariableReference
from playbooks.core.constants import EXECUTION_FINISHED
from playbooks.core.events import PlaybookEndEvent, PlaybookStartEvent
from playbooks.core.exceptions import ExecutionFinished, InteractiveInputRequired
from playbooks.debug.debug_handler import DebugHandler, NoOpDebugHandler
from playbooks.execution.call import PlaybookCall
from playbooks.execution.interpreter_prompt import InterpreterPrompt
from playbooks.execution.llm_response import LLMResponse, _strip_code_block_markers
from playbooks.execution.streaming_python_executor import (
    StreamingExecutionError,
    StreamingPythonExecutor,
)
from playbooks.llm.messages import (
    AssistantResponseLLMMessage,
    PlaybookImplementationLLMMessage,
)
from playbooks.llm.messages.types import ExecutionResultLLMMessage
from playbooks.utils.llm_config import LLMConfig
from playbooks.utils.llm_helper import ensure_async_iterable, get_completion

from .base import LLMExecution

if TYPE_CHECKING:
    from playbooks.agents.base_agent import Agent
    from playbooks.playbook.llm_playbook import LLMPlaybook

logger = logging.getLogger(__name__)


def _validate_interpreter_response(response: str) -> bool:
    """Validate that an LLM response is properly formatted for interpreter/playbook execution.

    Args:
        response: Raw LLM response string

    Returns:
        True if response is valid and should be cached, False otherwise
    """
    if not response or not response.strip():
        return False

    response = response.strip()

    # must start with ```python
    if not response.startswith("```python"):
        return False

    # must end with ```
    if not response.endswith("```"):
        return False

    # Strip code block markers if present
    processed = _strip_code_block_markers(response)

    # Check if it starts with the expected comment format
    lines = processed.strip().split("\n")
    if not lines:
        return False

    first_line = lines[0].strip()
    return first_line.startswith("# execution_id:")


class PlaybookLLMExecution(LLMExecution):
    """Playbook execution with defined steps.

    This is the core playbook mode - structured natural language functions
    with explicit steps that execute on LLMs. Aligns with ### Steps sections.

    This implements the unified execution strategy that replaced MarkdownPlaybookExecution.
    """

    def __init__(self, agent: "Agent", playbook: "LLMPlaybook") -> None:
        """Initialize playbook execution.

        Args:
            agent: The agent executing the playbook
            playbook: The LLM playbook to execute
        """
        super().__init__(agent, playbook)

        # Initialize streaming execution result holder
        self.streaming_execution_result = None

        # Initialize debug handler based on whether debug server is available
        if hasattr(agent, "program") and agent.program and agent.program._debug_server:
            # Check if debug server already has a debug handler
            if (
                hasattr(agent.program._debug_server, "debug_handler")
                and agent.program._debug_server.debug_handler
            ):
                # Use the existing debug handler from the debug server
                self.debug_handler = agent.program._debug_server.debug_handler
            else:
                # Create new debug handler and connect it
                self.debug_handler = DebugHandler(agent.program._debug_server)
                # Store reference in debug server for bidirectional communication
                agent.program._debug_server.debug_handler = self.debug_handler
        else:
            self.debug_handler = NoOpDebugHandler()

    async def pre_execute(self, call: PlaybookCall) -> None:
        """Prepare for playbook execution by adding implementation to call stack.

        Resolves description placeholders and adds playbook implementation
        message to the call stack for LLM context.

        Args:
            call: The playbook call being executed
        """
        llm_message = []
        markdown_for_llm = self.playbook.markdown  # Default to original markdown

        # Resolve description placeholders if present
        if self.playbook.description and "{" in self.playbook.description:
            context = ExpressionContext(agent=self.agent, call=call)
            resolved_description = await resolve_description_placeholders(
                self.playbook.description, context
            )

            markdown_for_llm = update_description_in_markdown(
                self.playbook.markdown, resolved_description
            )

        llm_message.append(
            f"{self.playbook.name} playbook implementation:\n\n````md\n{markdown_for_llm}\n````"
        )

        # Add a cached message whenever we add a stack frame
        llm_message.append("Executing " + str(call))

        # Create a PlaybookImplementationLLMMessage for semantic clarity
        playbook_impl_msg = PlaybookImplementationLLMMessage(
            content="\n\n".join(llm_message), playbook_name=self.playbook.name
        )

        # Add the message object directly to the call stack
        self.agent.call_stack.add_llm_message(playbook_impl_msg)

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the playbook with traditional step-by-step logic.

        Loops until execution completes, making LLM calls for each step.
        Handles streaming, code execution, and playbook completion.

        Args:
            *args: Positional arguments for the playbook
            **kwargs: Keyword arguments for the playbook

        Returns:
            Return value from the playbook execution (if any)
        """
        done = False
        return_value = None

        call = PlaybookCall(self.playbook.name, args, kwargs)
        await self.pre_execute(call)

        # Publish playbook start event
        self.agent.event_bus.publish(
            PlaybookStartEvent(
                session_id=self.agent.program.event_bus.session_id,
                agent_id=self.agent.id,
                playbook=self.playbook.name,
            )
        )

        instruction = f"Execute {str(call)} from step 01. Refer to {self.playbook.name} playbook implementation above."
        artifacts_to_load = []

        while not done:
            if self.agent.program.execution_finished:
                break

            description_paragraph = self.agent.description.split("\n\n")[0]

            # Extract playbook arguments to make available in generated code
            playbook_args = self._extract_playbook_arguments(call)

            # Make the LLM call and execute the generated code streaming
            raw_llm_response = await self.make_llm_call(
                instruction=instruction,
                agent_instructions=f"Remember: You are {str(self.agent)}. {description_paragraph}",
                artifacts_to_load=artifacts_to_load,
                playbook_args=playbook_args,
            )

            llm_response = await LLMResponse.create(
                raw_llm_response,
                event_bus=self.agent.event_bus,
                agent=self.agent,
            )

            # Update the AssistantResponseLLMMessage with the actual response
            self.llm_response_msg.set_content(llm_response.response)

            # Use the pre-computed execution result from streaming execution
            # The code was already executed incrementally during LLM streaming
            await llm_response.execute_generated_code(
                playbook_args=playbook_args,
                execution_result=self.streaming_execution_result,
            )

            # Clear streaming flag after code execution
            # This ensures next LLM call will properly stream its Say() calls
            if hasattr(self.agent, "_currently_streaming"):
                self.agent._currently_streaming = False

            # Check if code execution resulted in an error
            # If so, send error message back to LLM for correction
            if llm_response.has_execution_error():
                result = llm_response.execution_result
                error_content = (
                    f"ERROR: Code execution failed:\n\n"
                    f"{result.error_message}\n\n"
                    f"Please fix the error."
                )

                # Add error message to call stack for LLM to see
                error_msg = ExecutionResultLLMMessage(
                    content=error_content,
                    playbook_name=self.playbook.name,
                    success=False,
                )
                self.agent.call_stack.add_llm_message(error_msg)

                # Continue the loop to let LLM retry
                continue

            # Check if exiting program
            if llm_response.execution_result.exit_program:
                await self.agent.program.end_program()

            # Check if playbook finished
            if llm_response.execution_result.playbook_finished:
                return_value = llm_response.execution_result.return_value
                done = True

            # Update instruction
            instruction = []
            for loaded_artifact in artifacts_to_load:
                instruction.append(f"Loaded Artifact[{loaded_artifact}]")
            top_of_stack = self.agent.call_stack.peek()
            instruction.append(
                f"{str(top_of_stack)} was executed - "
                f"continue execution. Refer to {top_of_stack.instruction_pointer.playbook} playbook implementation above."
            )

            instruction = "\n".join(instruction)

        # Publish playbook end event
        call_stack_depth = len(self.agent.call_stack.frames)
        self.agent.event_bus.publish(
            PlaybookEndEvent(
                session_id=self.agent.program.event_bus.session_id,
                agent_id=self.agent.id,
                playbook=self.playbook.name,
                return_value=return_value,
                call_stack_depth=call_stack_depth,
            )
        )

        if self.agent.program.execution_finished:
            return EXECUTION_FINISHED

        return return_value

    async def make_llm_call(
        self,
        instruction: str,
        agent_instructions: str,
        artifacts_to_load: List[str] = None,
        playbook_args: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Make an LLM call for playbook execution.

        Increments execution_counter before the call and passes it to the prompt
        so the LLM can include it in the response (# execution_id: N).
        Uses streaming to handle Say() calls progressively.

        Args:
            instruction: Instruction for the LLM (what to do next)
            agent_instructions: Agent-specific instructions
            artifacts_to_load: List of artifact names to load into context

        Returns:
            Complete LLM response string

        Raises:
            ExecutionFinished: If max_llm_calls limit is exceeded
        """
        if artifacts_to_load is None:
            artifacts_to_load = []
        # Increment execution counter for this LLM call
        self.agent.execution_counter += 1
        execution_id = self.agent.execution_counter

        if execution_id > config.max_llm_calls:
            raise ExecutionFinished(
                f"Number of LLM calls excceed (config.max_llm_calls={config.max_llm_calls})"
            )

        # Flush pending meeting messages before constructing prompt
        # This ensures all agent communications are included in the LLM context
        if hasattr(self.agent, "meeting_manager") and self.agent.meeting_manager:
            current_meeting_id = (
                self.agent.meeting_manager.get_current_meeting_from_call_stack()
            )
            if current_meeting_id:
                await self.agent.meeting_manager.flush_pending_messages(
                    current_meeting_id
                )

        prompt = InterpreterPrompt(
            self.agent,
            self.agent.playbooks,
            self.playbook,
            instruction=instruction,
            agent_instructions=agent_instructions,
            artifacts_to_load=artifacts_to_load,
            agent_information=self.agent.get_compact_information(),
            other_agent_klasses_information=self.agent.other_agent_klasses_information(),
            execution_id=execution_id,  # NEW: Pass execution_id to prompt
        )

        # Create the user input message for this LLM call
        prompt.create_user_message()

        # Use streaming to handle Say() calls progressively
        return await self._stream_llm_response(
            prompt, playbook_args=playbook_args, execution_id=execution_id
        )

    async def _stream_llm_response(
        self,
        prompt: InterpreterPrompt,
        playbook_args: Optional[Dict[str, Any]] = None,
        execution_id: Optional[int] = None,
    ) -> str:
        """Stream LLM response and handle code execution and Say() calls progressively.

        Two-phase streaming approach:
        1. Pattern-based streaming (as tokens arrive) - detects Say("...") calls
        2. Incremental code execution - executes complete statements as they arrive

        The _currently_streaming flag mechanism:
        - When Say("human", "...") is pattern-detected during LLM token streaming,
          we stream it immediately to provide real-time feedback to the user
        - We set _currently_streaming=True to mark that this Say() was already displayed
        - Later, when the generated Python code executes, Say() checks this flag
        - If True, it skips streaming (already done) and just sends the message
        - This prevents double-display: once during LLM streaming, not again during execution
        - Only applies to human recipients - agent-to-agent messages use different path

        Args:
            prompt: InterpreterPrompt instance with messages and context
            playbook_args: Optional dict of playbook argument names to values

        Returns:
            Complete LLM response string (all chunks concatenated)
        """
        # Clear any previous streaming flag and set it for this streaming session
        # This ensures each LLM call has its own streaming cycle
        self.agent._currently_streaming = False

        # Initialize streaming Python executor for incremental code execution
        streaming_executor = StreamingPythonExecutor(
            self.agent, playbook_args, execution_id=execution_id
        )
        self.streaming_execution_result = None  # Will be set after execution

        buffer = ""
        in_say_call = False
        current_say_content = ""
        say_start_pos = 0
        say_recipient = ""
        say_stream_id = None  # Track stream ID for channel-based streaming
        processed_up_to = 0  # Track how much of buffer we've already processed
        say_has_placeholders = False  # Track if current Say has {$var} placeholders
        say_end_pattern = '")'  # Tracks closing pattern for Say content
        say_quote_type: Optional[str] = None  # "single" or "triple"

        # Get LLM messages
        messages = prompt.messages

        # Create an placeholder AssistantResponseLLMMessage so that it
        # appears before any messages from the execution results
        self.llm_response_msg = AssistantResponseLLMMessage("Thinking...")
        self.agent.call_stack.add_llm_message(self.llm_response_msg)

        # Create LLM config for the call
        execution_model = config.model.execution
        llm_config = LLMConfig(
            model=execution_model.name,
            provider=execution_model.provider,
            temperature=execution_model.temperature,
            max_completion_tokens=execution_model.max_completion_tokens,
        )

        # Set generation to None since we removed the creation code
        generation = None

        try:
            async for chunk in ensure_async_iterable(
                get_completion(
                    messages=messages,
                    llm_config=llm_config,
                    stream=True,
                    json_mode=False,
                    execution_id=execution_id,
                    event_bus=self.agent.event_bus,
                    agent_id=self.agent.id,
                    session_id=self.agent.program.event_bus.session_id,
                    response_validator=_validate_interpreter_response,
                )
            ):
                buffer += chunk

                # Update the AssistantResponseLLMMessage with the actual response
                self.llm_response_msg.set_content(buffer)

                # Feed chunk to streaming executor for incremental execution
                try:
                    await streaming_executor.add_chunk(chunk)
                    if (
                        hasattr(self.agent, "program")
                        and self.agent.program
                        and getattr(self.agent.program, "execution_finished", False)
                    ):
                        raise ExecutionFinished("Program execution finished")
                except StreamingExecutionError as e:
                    # Check if the underlying error is InteractiveInputRequired
                    # These should not be retried, they should fail immediately
                    if hasattr(e, "original_error"):
                        if isinstance(e.original_error, InteractiveInputRequired):
                            # Re-raise InteractiveInputRequired exceptions
                            raise e.original_error

                    # Execution error during streaming - stop processing
                    # The error details are already captured in streaming_executor.result
                    logger.error(f"Streaming execution error: {e}")
                    self.streaming_execution_result = streaming_executor.result
                    return buffer

                # Only look for new Say() calls in the unprocessed part of the buffer
                if not in_say_call:
                    # Updated pattern: no backticks (Python code format)
                    say_pattern = 'Say("'
                    say_match_pos = buffer.find(say_pattern, processed_up_to)
                    if say_match_pos != -1:
                        # Found potential Say call - now we need to extract the recipient
                        recipient_start = say_match_pos + len(say_pattern)

                        # Look for the end of the recipient (first argument)
                        recipient_end_pattern = '", "'
                        recipient_end_pos = buffer.find(
                            recipient_end_pattern, recipient_start
                        )

                        if recipient_end_pos != -1:
                            # Extract the recipient
                            say_recipient = buffer[recipient_start:recipient_end_pos]

                            # Determine if we should stream this Say() call
                            is_human_recipient = say_recipient.lower() in [
                                "user",
                                "human",
                            ]
                            enable_agent_streaming = (
                                self.agent.program.enable_agent_streaming
                                if self.agent.program
                                else False
                            )
                            should_attempt_streaming = (
                                is_human_recipient or enable_agent_streaming
                            )

                            if should_attempt_streaming:
                                in_say_call = True
                                say_start_pos = recipient_end_pos + len(
                                    recipient_end_pattern
                                )  # Position after recipient and ", "
                                say_end_pattern = '")'  # Default; may switch to triple
                                say_quote_type = None  # Determine once content arrives
                                current_say_content = ""
                                say_has_placeholders = False  # Reset for new Say call
                                processed_up_to = say_start_pos
                                # Use channel-based streaming infrastructure
                                stream_result = (
                                    await self.agent.start_streaming_say_via_channel(
                                        say_recipient
                                    )
                                )
                                say_stream_id = (
                                    stream_result.stream_id
                                    if stream_result.should_stream
                                    else None
                                )
                                # Set flag indicating we're actively streaming Say() calls
                                # This prevents double-processing when the generated code executes
                                # Only set if streaming is actually happening
                                if say_stream_id:
                                    self.agent._currently_streaming = True
                            else:
                                # Not streaming this Say call
                                processed_up_to = recipient_end_pos + len(
                                    recipient_end_pattern
                                )
                        else:
                            # Haven't found the end of recipient yet, continue processing
                            pass

                # Stream Say content if we're in a call
                if in_say_call:
                    # Determine quote style lazily to support triple-quoted strings
                    if say_quote_type is None:
                        # Need at least three characters to confirm triple quotes
                        if len(buffer) >= say_start_pos + 3 and buffer.startswith(
                            '""', say_start_pos
                        ):
                            say_quote_type = "triple"
                            say_end_pattern = '""")'
                            say_start_pos += 2  # Skip the extra two quotes
                            processed_up_to = say_start_pos
                        elif len(buffer) >= say_start_pos + 3:
                            say_quote_type = "single"
                            say_end_pattern = '")'
                        else:
                            # Not enough content yet to decide quote style
                            continue

                    # Look for the end of the Say call
                    # Updated pattern: no backticks (Python code format)
                    end_pos = buffer.find(say_end_pattern, say_start_pos)
                    if end_pos != -1:
                        # Found end - extract final content and complete
                        final_content = buffer[say_start_pos:end_pos]

                        # Resolve any {$var} placeholders in the message before streaming
                        if "{" in final_content:
                            final_content = await self._resolve_string_placeholders(
                                final_content
                            )

                        # If we deferred streaming due to placeholders, stream entire resolved content
                        # Otherwise, only stream the delta
                        if say_stream_id:
                            if say_has_placeholders:
                                # Stream entire resolved content
                                if final_content:
                                    await self.agent.stream_say_update_via_channel(
                                        say_stream_id, say_recipient, final_content
                                    )
                            else:
                                # Stream only new content since last update
                                if len(final_content) > len(current_say_content):
                                    new_content = final_content[
                                        len(current_say_content) :
                                    ]
                                    if new_content:
                                        await self.agent.stream_say_update_via_channel(
                                            say_stream_id, say_recipient, new_content
                                        )

                            await self.agent.complete_streaming_say_via_channel(
                                say_stream_id, say_recipient, final_content
                            )
                        in_say_call = False
                        current_say_content = ""
                        say_recipient = ""
                        say_stream_id = None
                        say_has_placeholders = False
                        processed_up_to = end_pos + len(say_end_pattern)
                        say_quote_type = None
                        say_end_pattern = '")'
                    else:
                        # Still streaming - extract new content since last update
                        # Only look at content between say_start_pos and end of buffer
                        # but make sure we don't include the closing quote if it's there
                        available_content = buffer[say_start_pos:]

                        # Check if content has placeholders - if so, defer streaming until complete
                        if "{" in available_content and not say_has_placeholders:
                            say_has_placeholders = True

                        # If we see the closing quote, don't include it in streaming
                        if available_content.endswith('")'):
                            available_content = available_content[:-2]  # Remove ")
                        elif available_content.endswith('"'):
                            available_content = available_content[:-1]  # Remove just "

                        # Don't stream incrementally if there are placeholders to resolve
                        # Wait until message is complete to resolve and stream
                        if not say_has_placeholders and say_stream_id:
                            # Don't stream if it ends with escape character (incomplete)
                            if not available_content.endswith("\\"):
                                # Trim trailing quotes that are part of triple-quoted closing
                                if available_content.endswith(say_end_pattern):
                                    available_content = available_content[
                                        : -len(say_end_pattern)
                                    ]
                                elif say_quote_type == "triple":
                                    if available_content.endswith('"""'):
                                        available_content = available_content[:-3]
                                    elif available_content.endswith('""'):
                                        available_content = available_content[:-2]
                                    elif available_content.endswith('"'):
                                        available_content = available_content[:-1]
                                else:
                                    if available_content.endswith('"'):
                                        available_content = available_content[:-1]
                                if len(available_content) > len(current_say_content):
                                    new_content = available_content[
                                        len(current_say_content) :
                                    ]
                                    current_say_content = available_content

                                    if new_content:
                                        await self.agent.stream_say_update_via_channel(
                                            say_stream_id, say_recipient, new_content
                                        )

            # If we ended while still in a Say call, complete it
            if in_say_call and say_stream_id:
                await self.agent.complete_streaming_say_via_channel(
                    say_stream_id, say_recipient, current_say_content
                )

            # Finalize streaming execution - execute any remaining buffered code
            self.streaming_execution_result = await streaming_executor.finalize()

            # Update generation with output and close context
            if generation:
                generation.update(output=buffer)
                generation.end()

        except ExecutionFinished as e:
            # Program execution finished, stop streaming
            raise e
        except Exception as e:
            # Unexpected error during streaming (not a StreamingExecutionError)
            logger.error(
                f"Unexpected error during LLM streaming: {type(e).__name__}: {e}"
            )
            # Try to finalize what we have so far
            try:
                self.streaming_execution_result = await streaming_executor.finalize()
            except Exception:
                # If finalization also fails, at least we have the original error
                pass
            # Update generation with error and close context
            try:
                if generation:
                    generation.update(output=buffer, status_message=str(e))
                    generation.end()
            except Exception:
                pass
            raise

        return buffer

    async def _resolve_string_placeholders(self, message: str) -> str:
        """Resolve {$var} placeholders in a message string during streaming.

        Args:
            message: Message string that may contain {$var} placeholders

        Returns:
            Message with placeholders resolved to actual values
        """
        if not message or "{" not in message:
            return message

        # Create expression context for resolution
        context = ExpressionContext(agent=self.agent, call=None)

        # Resolve placeholders
        resolved = await resolve_description_placeholders(message, context)
        return resolved

    def _extract_playbook_arguments(self, call: PlaybookCall) -> Dict[str, Any]:
        """Extract and resolve playbook arguments to a dict.

        Takes the PlaybookCall's args and kwargs and binds them to parameter
        names using the playbook's signature. Resolves LiteralValue and
        VariableReference types to actual values.

        Args:
            call: The PlaybookCall containing args and kwargs

        Returns:
            Dictionary mapping parameter names to resolved values
        """
        result = {}

        # Get playbook signature
        if not hasattr(self.playbook, "signature") or not self.playbook.signature:
            return result

        # Get args and kwargs from call
        args = call.args if hasattr(call, "args") and call.args else []
        kwargs = call.kwargs if hasattr(call, "kwargs") and call.kwargs else {}

        # Bind arguments to parameter names
        bound_params = bind_call_parameters(self.playbook.signature, args, kwargs)

        # Resolve VariableReference and LiteralValue types to actual values
        for param_name, value in bound_params.items():
            if isinstance(value, LiteralValue):
                result[param_name] = value.value
            elif isinstance(value, VariableReference):
                # Resolve the variable reference
                ref = value.reference
                # Remove $ prefix if present
                if ref.startswith("$"):
                    ref = ref[1:]
                try:
                    # Try to get from state variables
                    if self.agent.state and hasattr(self.agent.state, ref):
                        var = getattr(self.agent.state, ref)
                        result[param_name] = var
                    else:
                        # Variable not found, store the reference as-is
                        result[param_name] = value
                except Exception:
                    # If can't resolve, store the reference as-is
                    result[param_name] = value
            else:
                # Already a resolved value
                result[param_name] = value

        # Set state variables (parameters with $ prefix in signature) on self.state
        # Check if the original signature has $ prefix for each parameter
        for param_name, value in result.items():
            if (
                f"${param_name}" in self.playbook.signature
                or f"${param_name}:" in self.playbook.signature
            ):
                # This is a state variable, set it on self.state
                setattr(self.agent.state, param_name, value)

        return result
