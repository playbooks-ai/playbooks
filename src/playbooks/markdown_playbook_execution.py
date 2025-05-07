from typing import List

from playbooks.ai_agent import AIAgent
from playbooks.config import LLMConfig
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

    async def execute(self, *args, **kwargs):
        done = False
        return_value = None

        call = PlaybookCall(self.playbook.klass, args, kwargs)

        instruction = f"Execute {str(call)}"
        artifacts_to_load = []
        while not done:
            llm_response = LLMResponse(
                await self.make_llm_call(
                    instruction=instruction,
                    agent_instructions=self.agent.description,
                    artifacts_to_load=artifacts_to_load,
                )
            )

            user_inputs = []
            artifacts_to_load = []
            for line in llm_response.lines:
                if "`SaveArtifact(" not in line.text:
                    self.agent.state.session_log.append(
                        SessionLogItemMessage(line.text),
                        level=SessionLogItemLevel.LOW,
                    )

                # Replace the current call stack frame with the last executed step
                if line.steps:
                    last_step = line.steps[-1]
                    self.agent.state.call_stack.advance_instruction_pointer(last_step)

                # Update variables
                if len(line.vars) > 0:
                    self.agent.state.variables.update(line.vars.to_dict())

                # Execute playbook calls
                if line.playbook_calls:
                    for playbook_call in line.playbook_calls:
                        if playbook_call.playbook_klass == "Return":
                            if playbook_call.args:
                                return_value = playbook_call.args[0]
                        elif playbook_call.playbook_klass == "LoadArtifact":
                            artifacts_to_load.append(playbook_call.args[0])
                        else:
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
                    user_input = await self.agent.WaitForMessage("human")
                    user_inputs.append(user_input)
                elif line.playbook_finished:
                    done = True
                    break

                # Raise an exception if line.finished is true
                if line.exit_program:
                    raise ExecutionFinished("Execution finished.")

            # Update instruction
            instruction = []
            for loaded_artifact in artifacts_to_load:
                instruction.append(f"Loaded Artifact[{loaded_artifact}]")
            instruction.append(
                f"{str(self.agent.state.call_stack.peek())} was executed - continue execution."
            )
            if user_inputs:
                instruction.append(f"User said: {' '.join(user_inputs)}")

            instruction = "\n".join(instruction)

        if self.agent.state.call_stack.is_empty():
            raise ExecutionFinished("Call stack is empty. Execution finished.")
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
