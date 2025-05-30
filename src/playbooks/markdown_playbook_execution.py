from typing import List

from playbooks.ai_agent import AIAgent
from playbooks.config import LLMConfig
from playbooks.debug.debug_handler import DebugHandler, NoOpDebugHandler
from playbooks.events import (
    LineExecutedEvent,
    PlaybookEndEvent,
    PlaybookStartEvent,
)
from playbooks.interpreter_prompt import InterpreterPrompt
from playbooks.llm_response import LLMResponse
from playbooks.playbook import Playbook
from playbooks.playbook_call import PlaybookCall
from playbooks.session_log import SessionLogItemLevel, SessionLogItemMessage
from playbooks.utils.llm_helper import get_completion


class ExecutionFinished(Exception):
    """Custom exception to indicate that the playbook execution is finished."""

    pass


class MarkdownPlaybookExecution:
    def __init__(self, agent: AIAgent, playbook_klass: str, llm_config: LLMConfig):
        self.agent: AIAgent = agent
        self.playbook: Playbook = agent.playbooks[playbook_klass]
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
            PlaybookStartEvent(playbook=self.playbook.klass)
        )

        call = PlaybookCall(self.playbook.klass, args, kwargs)

        instruction = f"Execute {str(call)}"
        artifacts_to_load = []
        await self.debug_handler.handle_execution_start(
            self.agent.state.call_stack.peek(),
            self.agent.state.call_stack.peek(),
            self.agent.state.event_bus,
        )

        while not done:
            llm_response = LLMResponse(
                await self.make_llm_call(
                    instruction=instruction,
                    agent_instructions=self.agent.description,
                    artifacts_to_load=artifacts_to_load,
                ),
                event_bus=self.agent.state.event_bus,
                agent=self.agent,
            )
            # print(f"[EXECUTE] llm_response: {llm_response.response}")

            user_inputs = []
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
                # print(f"[EXECUTE] line: {line.text}")
                if "`SaveArtifact(" not in line.text:
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
                    self.agent.state.variables.update(line.vars.to_dict())

                # Execute playbook calls
                if line.playbook_calls:
                    for playbook_call in line.playbook_calls:
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
                    # print("[EXECUTE] waiting for user input")
                    user_input = await self.agent.WaitForMessage("human")
                    user_inputs.append(user_input)
                elif line.playbook_finished:
                    # print("[EXECUTE] playbook_finished")
                    done = True
                    break

                # Raise an exception if line.finished is true
                if line.exit_program:
                    # print("[EXECUTE] exit_program")
                    raise ExecutionFinished("Execution finished.")

            # Update instruction
            instruction = []
            for loaded_artifact in artifacts_to_load:
                instruction.append(f"Loaded Artifact[{loaded_artifact}]")
            instruction.append(
                f"{str(self.agent.state.call_stack.peek())} was executed - "
                "continue execution."
            )
            if user_inputs:
                instruction.append(f"User said: {' '.join(user_inputs)}")

            instruction = "\n".join(instruction)

        if self.agent.state.call_stack.is_empty():
            raise ExecutionFinished("Call stack is empty. Execution finished.")

        # Publish playbook end event
        call_stack_depth = len(self.agent.state.call_stack.frames)

        self.agent.state.event_bus.publish(
            PlaybookEndEvent(
                playbook=self.playbook.klass,
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
        )

        chunks = [
            chunk
            for chunk in get_completion(
                messages=prompt.messages,
                llm_config=self.llm_config,
                stream=False,
                json_mode=False,  # interpreter calls produce markdown
                langfuse_span=self.agent.state.call_stack.peek().langfuse_span,
            )
        ]
        return "".join(chunks)
