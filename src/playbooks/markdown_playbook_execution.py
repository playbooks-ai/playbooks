from typing import List

from playbooks.agents import LocalAIAgent
from playbooks.config import LLMConfig
from playbooks.constants import EXECUTION_FINISHED
from playbooks.debug.debug_handler import DebugHandler, NoOpDebugHandler
from playbooks.enums import LLMMessageRole
from playbooks.events import (
    LineExecutedEvent,
    PlaybookEndEvent,
    PlaybookStartEvent,
)
from playbooks.exceptions import ExecutionFinished
from playbooks.interpreter_prompt import InterpreterPrompt
from playbooks.llm_response import LLMResponse
from playbooks.playbook import MarkdownPlaybook
from playbooks.playbook_call import PlaybookCall
from playbooks.session_log import SessionLogItemLevel, SessionLogItemMessage
from playbooks.utils.llm_helper import get_completion
from playbooks.utils.spec_utils import SpecUtils


class MarkdownPlaybookExecution:
    def __init__(self, agent: LocalAIAgent, playbook_name: str, llm_config: LLMConfig):
        self.agent: LocalAIAgent = agent
        self.playbook: MarkdownPlaybook = agent.playbooks[playbook_name]
        self.llm_config: LLMConfig = llm_config

        # Initialize debug handler
        self.debug_handler = (
            DebugHandler(agent.program._debug_server)
            if agent.program._debug_server
            else NoOpDebugHandler()
        )

    async def execute(self, *args, **kwargs):
        done = False
        return_value = None

        # print(f"[EXECUTE] {args} {kwargs}")
        # Reset debug handler for each execution
        self.debug_handler.reset_for_execution()

        # Publish playbook start event
        self.agent.state.event_bus.publish(
            PlaybookStartEvent(playbook=self.playbook.name)
        )

        call = PlaybookCall(self.playbook.name, args, kwargs)

        instruction = f"Execute {str(call)} from step 01"
        artifacts_to_load = []
        await self.debug_handler.handle_execution_start(
            self.agent.state.call_stack.peek(),
            self.agent.state.call_stack.peek(),
            self.agent.state.event_bus,
        )

        while not done:
            if self.agent.program.execution_finished:
                break

            llm_response = LLMResponse(
                await self.make_llm_call(
                    instruction=instruction,
                    agent_instructions=f"Remember: You are {str(self.agent)}. {self.agent.description}",
                    artifacts_to_load=artifacts_to_load,
                ),
                event_bus=self.agent.state.event_bus,
                agent=self.agent,
            )

            self.agent.state.call_stack.peek().add_cached_llm_message(
                llm_response.response, role=LLMMessageRole.ASSISTANT
            )
            # print(f"[EXECUTE] llm_response: {llm_response.response}")

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

                # print(f"[EXECUTE] line: {line.text}")
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

                for i in range(len(line.steps)):
                    step = line.steps[i]
                    if i == len(line.steps) - 1:
                        # next_step = next_steps[step]
                        next_step = step
                        # print(f"[EXECUTE] advance_instruction_pointer to: {next_step}")
                        self.agent.state.call_stack.advance_instruction_pointer(
                            next_step
                        )
                        # Handle debug operations at start of loop
                        await self.debug_handler.handle_execution_start(
                            step, step, self.agent.state.event_bus
                        )
                    else:
                        # next_step = next_steps[step]
                        next_step = step
                        # print(f"[EXECUTE] advance_instruction_pointer to: {next_step}")
                        self.agent.state.call_stack.advance_instruction_pointer(
                            next_step
                        )
                        await self.debug_handler.handle_execution_start(
                            step, next_step, self.agent.state.event_bus
                        )

                # Replace the current call stack frame with the last executed step
                if line.steps:
                    # print(f"[EXECUTE] line.steps: {line.steps}")
                    # Remove the redundant loop - we only care about the last step
                    last_step = line.steps[-1]

                    # Check for breakpoints
                    # print(f"[EXECUTE] last_step: {last_step}")
                    await self.debug_handler.handle_breakpoint(
                        last_step.source_line_number, self.agent.state.event_bus
                    )

                    # Publish line executed event
                    self.agent.state.event_bus.publish(
                        LineExecutedEvent(
                            step=str(last_step),
                            source_line_number=last_step.source_line_number,
                            text=line.text,
                        )
                    )

                # Update variables
                if len(line.vars) > 0:
                    self.agent.state.variables.update(line.vars)

                # Execute playbook calls
                if line.playbook_calls:
                    for playbook_call in line.playbook_calls:
                        if self.agent.program.execution_finished:
                            break

                        if playbook_call.playbook_klass == "Return":
                            # print(f"[EXECUTE] Return: {playbook_call.args}")
                            if playbook_call.args:
                                return_value = playbook_call.args[0]
                        elif playbook_call.playbook_klass == "LoadArtifact":
                            # print(f"[EXECUTE] LoadArtifact: {playbook_call.args}")
                            artifacts_to_load.append(playbook_call.args[0])
                        else:
                            # print(
                            #     f"[EXECUTE] execute_playbook: {playbook_call.playbook_klass}"
                            # )
                            await self.agent.execute_playbook(
                                playbook_call.playbook_klass,
                                playbook_call.args,
                                playbook_call.kwargs,
                            )

                # Return value
                if line.return_value:
                    return_value = line.return_value
                    str_return_value = str(return_value)
                    if (
                        str_return_value.startswith("$")
                        and str_return_value in self.agent.state.variables
                    ):
                        return_value = self.agent.state.variables[
                            str_return_value
                        ].value

                # Wait for external event
                if line.wait_for_user_input:
                    # print(f"\n{str(self.agent)}: [EXECUTE] waiting for user input")
                    await self.agent.WaitForMessage("human")
                    # print(f"\n{str(self.agent)}: [EXECUTE] user input: {user_input}")
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
                            # print(
                            #     f"\n{str(self.agent)}: [EXECUTE] waiting for meeting messages from {meeting_id}"
                            # )
                            await self.agent.WaitForMessage(f"meeting {meeting_id}")
                            # print(
                            #     f"\n{str(self.agent)}: [EXECUTE] agent input: {agent_input}"
                            # )
                        else:
                            # print(
                            #     f"\n{str(self.agent)}: [EXECUTE] waiting for agent input from {target_agent_id}"
                            # )
                            await self.agent.WaitForMessage(target_agent_id)
                            # print(
                            #     f"\n{str(self.agent)}: [EXECUTE] agent input: {agent_input}"
                            # )
                elif line.playbook_finished:
                    # print("[EXECUTE] playbook_finished")
                    done = True

                # Raise an exception if line.finished is true
                if line.exit_program:
                    # print("[EXECUTE] exit_program")
                    raise ExecutionFinished(EXECUTION_FINISHED)

            # Update instruction
            instruction = []
            for loaded_artifact in artifacts_to_load:
                instruction.append(f"Loaded Artifact[{loaded_artifact}]")
            instruction.append(
                f"{str(self.agent.state.call_stack.peek())} was executed - "
                "continue execution."
            )

            instruction = "\n".join(instruction)

        if self.agent.program.execution_finished:
            return EXECUTION_FINISHED

        if self.agent.state.call_stack.is_empty():
            raise ExecutionFinished(f"Call stack is empty. {EXECUTION_FINISHED}.")

        # Publish playbook end event
        call_stack_depth = len(self.agent.state.call_stack.frames)

        self.agent.state.event_bus.publish(
            PlaybookEndEvent(
                playbook=self.playbook.name,
                return_value=return_value,
                call_stack_depth=call_stack_depth,
            )
        )

        # Handle any debug cleanup
        await self.debug_handler.handle_execution_end()

        return return_value

    async def make_llm_call(
        self,
        instruction: str,
        agent_instructions: str,
        artifacts_to_load: List[str] = [],
    ):
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

        for chunk in get_completion(
            messages=prompt.messages,
            llm_config=self.llm_config,
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
                    if len(final_content) > len(current_say_content):
                        new_content = final_content[len(current_say_content) :]
                        if new_content:
                            await self.agent.stream_say_update(new_content)

                    await self.agent.complete_streaming_say()
                    in_say_call = False
                    current_say_content = ""
                    say_recipient = ""
                    processed_up_to = end_pos + len(end_pattern)
                else:
                    # Still streaming - extract new content since last update
                    # Only look at content between say_start_pos and end of buffer
                    # but make sure we don't include the closing quote if it's there
                    available_content = buffer[say_start_pos:]

                    # If we see the closing quote, don't include it in streaming
                    if available_content.endswith('")'):
                        available_content = available_content[:-2]  # Remove ")
                    elif available_content.endswith('"'):
                        available_content = available_content[:-1]  # Remove just "

                    # Don't stream if it ends with escape character (incomplete)
                    if not available_content.endswith("\\"):
                        if len(available_content) > len(current_say_content):
                            new_content = available_content[len(current_say_content) :]
                            current_say_content = available_content

                            if new_content:
                                await self.agent.stream_say_update(new_content)

        # If we ended while still in a Say call, complete it
        if in_say_call:
            await self.agent.complete_streaming_say()

        return buffer

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
