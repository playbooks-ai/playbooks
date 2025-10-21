"""Traditional playbook execution with defined steps."""

import logging
from typing import TYPE_CHECKING, Any, List

from ..constants import EXECUTION_FINISHED
from ..debug.debug_handler import DebugHandler, NoOpDebugHandler
from ..exceptions import ExecutionFinished
from ..interpreter_prompt import InterpreterPrompt
from ..llm_messages import AssistantResponseLLMMessage, PlaybookImplementationLLMMessage
from ..llm_response import LLMResponse
from ..playbook_call import PlaybookCall
from ..session_log import SessionLogItemLevel, SessionLogItemMessage
from ..utils.expression_engine import (
    ExpressionContext,
    resolve_description_placeholders,
    update_description_in_markdown,
)
from ..utils.llm_config import LLMConfig
from ..utils.llm_helper import get_completion
from ..utils.spec_utils import SpecUtils
from .base import LLMExecution

if TYPE_CHECKING:
    from ..agents.base_agent import Agent
    from ..playbook.llm_playbook import LLMPlaybook

logger = logging.getLogger(__name__)


class PlaybookLLMExecution(LLMExecution):
    """Playbook execution with defined steps.

    This is the core playbook mode - structured natural language functions
    with explicit steps that execute on LLMs. Aligns with ### Steps sections.

    This implements the unified execution strategy that replaced MarkdownPlaybookExecution.
    """

    def __init__(self, agent: "Agent", playbook: "LLMPlaybook"):
        """Initialize playbook execution.

        Args:
            agent: The agent executing the playbook
            playbook: The LLM playbook to execute
        """
        super().__init__(agent, playbook)

        # Initialize debug handler based on whether debug server is available
        # debug(
        #     f"[DEBUG] Initializing debug handler - agent has program: {hasattr(agent, 'program')}, program exists: {agent.program if hasattr(agent, 'program') else 'No'}, debug server exists: {agent.program._debug_server if hasattr(agent, 'program') and agent.program else 'No'}",
        # )
        if hasattr(agent, "program") and agent.program and agent.program._debug_server:
            # Check if debug server already has a debug handler
            if (
                hasattr(agent.program._debug_server, "debug_handler")
                and agent.program._debug_server.debug_handler
            ):
                # Use the existing debug handler from the debug server
                # debug(
                #     "[DEBUG] Using existing DebugHandler from debug server",
                # )
                self.debug_handler = agent.program._debug_server.debug_handler
            else:
                # Create new debug handler and connect it
                # debug(
                #     "[DEBUG] Creating new DebugHandler and connecting to debug server",
                # )
                self.debug_handler = DebugHandler(agent.program._debug_server)
                # Store reference in debug server for bidirectional communication
                agent.program._debug_server.debug_handler = self.debug_handler
                # debug(
                #     "[DEBUG] New debug handler connected to debug server",
                # )
        else:
            self.debug_handler = NoOpDebugHandler()

    async def pre_execute(self, call: PlaybookCall) -> None:
        llm_message = []
        markdown_for_llm = self.playbook.markdown  # Default to original markdown

        # Resolve description placeholders if present
        if self.playbook.description and "{" in self.playbook.description:
            context = ExpressionContext(
                agent=self.agent, state=self.agent.state, call=call
            )
            resolved_description = await resolve_description_placeholders(
                self.playbook.description, context
            )

            markdown_for_llm = update_description_in_markdown(
                self.playbook.markdown, resolved_description
            )

        llm_message.append(
            f"{self.playbook.name} playbook implementation:\n\n```md\n{markdown_for_llm}\n```"
        )

        # Add a cached message whenever we add a stack frame
        llm_message.append("Executing " + str(call))

        # Create a PlaybookImplementationLLMMessage for semantic clarity
        playbook_impl_msg = PlaybookImplementationLLMMessage(
            content="\n\n".join(llm_message), playbook_name=self.playbook.name
        )

        # Add the message object directly to the call stack
        self.agent.state.call_stack.add_llm_message(playbook_impl_msg)

    async def execute(self, *args, **kwargs) -> Any:
        """Execute the playbook with traditional step-by-step logic."""
        done = False
        return_value = None

        call = PlaybookCall(self.playbook.name, args, kwargs)
        await self.pre_execute(call)

        instruction = f"Execute {str(call)} from step 01. Refer to {self.playbook.name} playbook implementation above."
        artifacts_to_load = []

        while not done:
            if self.agent.program.execution_finished:
                break

            description_paragraph = self.agent.description.split("\n\n")[0]
            llm_response = await LLMResponse.create(
                await self.make_llm_call(
                    instruction=instruction,
                    agent_instructions=f"Remember: You are {str(self.agent)}. {description_paragraph}",
                    artifacts_to_load=artifacts_to_load,
                ),
                event_bus=self.agent.state.event_bus,
                agent=self.agent,
            )

            # Create an AssistantResponseLLMMessage for semantic clarity
            llm_response_msg = AssistantResponseLLMMessage(llm_response.response)

            # Add the message object directly to the call stack
            self.agent.state.call_stack.add_llm_message(llm_response_msg)

            artifacts_to_load = []

            all_steps = []
            for line in llm_response.lines:
                for step in line.steps:
                    all_steps.append(step)
            next_steps = {}
            for i in range(len(all_steps)):
                if i == len(all_steps) - 1:
                    next_steps[all_steps[i]] = all_steps[i]
                else:
                    next_steps[all_steps[i]] = all_steps[i + 1]

            for line in llm_response.lines:
                if self.agent.program.execution_finished:
                    break

                if "`SaveArtifact(" not in line.text:
                    for step in line.steps:
                        if step.step:
                            self.agent.state.session_log.append(
                                SessionLogItemMessage(
                                    f"{self.playbook.name}:{step.step.raw_text}"
                                ),
                                level=SessionLogItemLevel.HIGH,
                            )
                    self.agent.state.session_log.append(
                        SessionLogItemMessage(line.text),
                        level=SessionLogItemLevel.LOW,
                    )

                # Process steps but only call handle_execution_start once per line
                for i in range(len(line.steps)):
                    # debug("Execution step", step_index=i, step=str(line.steps[i]))
                    step = line.steps[i]
                    if i == len(line.steps) - 1:
                        next_step = step.copy()
                        # debug("Next step prepared", next_step=str(next_step))
                    else:
                        next_step = step

                    self.agent.state.call_stack.advance_instruction_pointer(next_step)

                # Replace the current call stack frame with the last executed step
                if line.steps:
                    # last_step = line.steps[-1].copy()

                    # debug(
                    #     "Call handle_step",
                    #     last_step=str(last_step),
                    #     next_step=str(next_step),
                    # )

                    for step in line.steps:
                        # debug(f"Agent {self.agent.id} pause if needed on step {step}")
                        await self.debug_handler.pause_if_needed(
                            instruction_pointer=step,
                            agent_id=self.agent.id,
                        )
                        # debug(
                        #     f"Agent {self.agent.id} pause if needed on step {step} done"
                        # )

                # Update variables
                if len(line.vars) > 0:
                    self.agent.state.variables.update(line.vars)

                # Execute playbook calls
                if line.playbook_calls:
                    for playbook_call in line.playbook_calls:
                        if self.agent.program.execution_finished:
                            break

                        # debug("Playbook call", playbook_call=str(playbook_call))
                        if playbook_call.playbook_klass == "Return":
                            if playbook_call.args:
                                return_value = playbook_call.args[0]
                        elif playbook_call.playbook_klass == "LoadArtifact":
                            artifacts_to_load.append(playbook_call.args[0])
                        else:
                            if playbook_call.playbook_klass == "Say":
                                playbook_call.kwargs["already_streamed"] = True
                            success, result = await self.agent.execute_playbook(
                                playbook_call.playbook_klass,
                                playbook_call.args,
                                playbook_call.kwargs,
                            )
                            # Store result in variable if assignment was specified
                            if playbook_call.variable_to_assign:
                                # Only assign if result isn't already the variable name itself
                                # (which indicates an artifact was already created and stored)
                                if result != playbook_call.variable_to_assign:
                                    self.agent.state.variables[
                                        playbook_call.variable_to_assign
                                    ] = result

                # Return value
                if line.return_value:
                    return_value = line.return_value
                    str_return_value = str(return_value)
                    # If it's a variable reference or expression (starts with $), evaluate it
                    if str_return_value.startswith("$"):
                        context = ExpressionContext(
                            agent=self.agent, state=self.agent.state, call=None
                        )
                        return_value = context.evaluate_expression(str_return_value)

                # Wait for external event
                if line.wait_for_user_input:
                    await self.agent.WaitForMessage("human")
                elif line.wait_for_agent_input:
                    target_agent_id = self._resolve_yld_target(
                        line.wait_for_agent_target
                    )
                    if target_agent_id:
                        # Check if this is a meeting target
                        if SpecUtils.is_meeting_spec(target_agent_id):
                            meeting_id = SpecUtils.extract_meeting_id(target_agent_id)
                            if meeting_id == "current":
                                meeting_id = (
                                    self.agent.state.call_stack.peek().meeting_id
                                )
                            await self.agent.WaitForMessage(f"meeting {meeting_id}")
                        else:
                            await self.agent.WaitForMessage(target_agent_id)
                elif line.playbook_finished:
                    done = True

                # Raise an exception if line.finished is true
                if line.exit_program:
                    raise ExecutionFinished(EXECUTION_FINISHED)

            # Update instruction
            instruction = []
            for loaded_artifact in artifacts_to_load:
                instruction.append(f"Loaded Artifact[{loaded_artifact}]")
            top_of_stack = self.agent.state.call_stack.peek()
            instruction.append(
                f"{str(top_of_stack)} was executed - "
                f"continue execution. Refer to {top_of_stack.instruction_pointer.playbook} playbook implementation above."
            )

            instruction = "\n".join(instruction)

        if self.agent.program.execution_finished:
            return EXECUTION_FINISHED

        return return_value

    async def make_llm_call(
        self,
        instruction: str,
        agent_instructions: str,
        artifacts_to_load: List[str] = [],
    ):
        """Make an LLM call for playbook execution."""

        prompt = InterpreterPrompt(
            self.agent.state,
            self.agent.playbooks,
            self.playbook,
            instruction=instruction,
            agent_instructions=agent_instructions,
            artifacts_to_load=artifacts_to_load,
            agent_information=self.agent.get_compact_information(),
            other_agent_klasses_information=self.agent.other_agent_klasses_information(),
            trigger_instructions=self.agent.all_trigger_instructions(),
        )

        # Use streaming to handle Say() calls progressively
        return await self._stream_llm_response(prompt)

    async def _stream_llm_response(self, prompt):
        """Stream LLM response and handle Say() calls progressively."""
        buffer = ""
        in_say_call = False
        current_say_content = ""
        say_start_pos = 0
        say_recipient = ""
        processed_up_to = 0  # Track how much of buffer we've already processed
        say_has_placeholders = False  # Track if current Say has {$var} placeholders

        for chunk in get_completion(
            messages=prompt.messages,
            llm_config=LLMConfig(),
            stream=True,
            json_mode=False,
            langfuse_span=self.agent.state.call_stack.peek().langfuse_span,
        ):
            buffer += chunk

            # Only look for new Say() calls in the unprocessed part of the buffer
            if not in_say_call:
                say_pattern = '`Say("'
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

                        # Only start streaming if recipient is user, human, or Human
                        if say_recipient.lower() in ["user", "human"]:
                            in_say_call = True
                            say_start_pos = recipient_end_pos + len(
                                recipient_end_pattern
                            )  # Position after recipient and ", "
                            current_say_content = ""
                            say_has_placeholders = False  # Reset for new Say call
                            processed_up_to = say_start_pos
                            await self.agent.start_streaming_say(say_recipient)
                        else:
                            # Not a user/human recipient, skip streaming for this Say call
                            processed_up_to = recipient_end_pos + len(
                                recipient_end_pattern
                            )
                    else:
                        # Haven't found the end of recipient yet, continue processing
                        pass

            # Stream Say content if we're in a call
            if in_say_call:
                # Look for the end of the Say call
                end_pattern = '")'
                end_pos = buffer.find(end_pattern, say_start_pos)
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
                    if say_has_placeholders:
                        # Stream entire resolved content
                        if final_content:
                            await self.agent.stream_say_update(final_content)
                    else:
                        # Stream only new content since last update
                        if len(final_content) > len(current_say_content):
                            new_content = final_content[len(current_say_content) :]
                            if new_content:
                                await self.agent.stream_say_update(new_content)

                    await self.agent.complete_streaming_say()
                    in_say_call = False
                    current_say_content = ""
                    say_recipient = ""
                    say_has_placeholders = False
                    processed_up_to = end_pos + len(end_pattern)
                else:
                    # Still streaming - extract new content since last update
                    # Only look at content between say_start_pos and end of buffer
                    # but make sure we don't include the closing quote if it's there
                    available_content = buffer[say_start_pos:]

                    # Check if content has placeholders - if so, defer streaming until complete
                    if "{$" in available_content and not say_has_placeholders:
                        say_has_placeholders = True

                    # If we see the closing quote, don't include it in streaming
                    if available_content.endswith('")'):
                        available_content = available_content[:-2]  # Remove ")
                    elif available_content.endswith('"'):
                        available_content = available_content[:-1]  # Remove just "

                    # Don't stream incrementally if there are placeholders to resolve
                    # Wait until message is complete to resolve and stream
                    if not say_has_placeholders:
                        # Don't stream if it ends with escape character (incomplete)
                        if not available_content.endswith("\\"):
                            if len(available_content) > len(current_say_content):
                                new_content = available_content[
                                    len(current_say_content) :
                                ]
                                current_say_content = available_content

                                if new_content:
                                    await self.agent.stream_say_update(new_content)

        # If we ended while still in a Say call, complete it
        if in_say_call:
            await self.agent.complete_streaming_say()

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
        context = ExpressionContext(agent=self.agent, state=self.agent.state, call=None)

        # Resolve placeholders
        resolved = await resolve_description_placeholders(message, context)
        return resolved

    def _resolve_yld_target(self, target: str) -> str:
        """Resolve a YLD target to an agent ID.

        Args:
            target: The YLD target specification

        Returns:
            Resolved agent ID or None if target couldn't be resolved
        """
        if not target:
            return None

        # Use the unified target resolver with no fallback for YLD
        # (YLD should be explicit about what it's waiting for)
        return self.agent.resolve_target(target, allow_fallback=False)
