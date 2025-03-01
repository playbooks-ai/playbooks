"""Interpreter execution module for the interpreter."""

import re
from typing import TYPE_CHECKING, Dict, Generator, List, Tuple

import yaml

from ..call_stack import CallStackFrame, InstructionPointer
from ..enums import PlaybookExecutionType
from ..llm_call import LLMCall
from ..trace_mixin import TraceMixin
from ..types import AgentResponseChunk, ToolCall
from ..utils.llm_helper import get_messages_for_prompt

if TYPE_CHECKING:
    from ..config import LLMConfig
    from ..playbook import Playbook
    from .interpreter import Interpreter


class InterpreterExecution(TraceMixin):
    """Represents the execution of an interpreter."""

    def __init__(
        self,
        interpreter: "Interpreter",
        playbooks: Dict[str, "Playbook"],
        current_playbook: "Playbook",
        instruction: str,
        llm_config: "LLMConfig" = None,
        stream: bool = False,
    ):
        """Initialize an interpreter execution.

        Args:
            interpreter: The interpreter executing the playbook.
            playbooks: The available playbooks.
            current_playbook: The current playbook being executed.
            instruction: The instruction to execute.
            llm_config: The LLM configuration.
            stream: Whether to stream the response.
        """
        super().__init__()
        self.interpreter: "Interpreter" = interpreter
        self.playbooks: Dict[str, "Playbook"] = playbooks
        self.current_playbook: "Playbook" = current_playbook
        self.instruction: str = instruction
        self.llm_config: "LLMConfig" = llm_config
        self.stream: bool = stream
        self.wait_for_external_event: bool = False

    def parse_response(self, response: str) -> Tuple[List[ToolCall], str, Dict]:
        """Parse the response from the LLM.

        Args:
            response: The response from the LLM.

        Returns:
            A tuple of tool calls, the last executed step, and updated variables.
        """
        # First try to extract yaml content between triple backticks
        yaml_match = re.search(r"```(?:yaml)?\n(.*?)```", response, re.DOTALL)
        if yaml_match:
            yaml_content = yaml_match.group(1)
        else:
            # If no triple backticks found, try to parse the entire response as YAML
            yaml_content = response

        try:
            parsed = yaml.safe_load(yaml_content)
            if not parsed or not isinstance(parsed, list):
                raise ValueError("Empty YAML content")
        except yaml.YAMLError as err:
            raise ValueError(f"Invalid YAML content: {yaml_content}") from err

        tool_calls = []
        last_executed_step = None
        updated_variables = {}

        abort_execution = False
        for step_dict in parsed:
            if abort_execution:
                break
            step = next(iter(step_dict))
            step = step.strip()
            # Import here to avoid circular imports
            from .step_execution import StepExecution

            step_execution = StepExecution(step, metadata=step_dict)
            self.trace(step_execution)

            last_executed_step = step
            step_trace = step_dict[step]

            # Sometimes llm returns a dict instead of a list, work around that
            if isinstance(step_trace, dict):
                step_trace = [{key: value} for key, value in step_trace.items()]

            for item in step_trace:
                if abort_execution:
                    break
                if "call" in item:
                    tool_calls.append(
                        ToolCall(
                            fn=item["call"]["fn"],
                            args=item["call"].get("args", []),
                            kwargs=item["call"].get("kwargs", {}),
                        )
                    )

                    if item["call"]["fn"] in self.playbooks:
                        # If this is a playbook call, ignore rest of the trace
                        # because we will execute the playbook now
                        if (
                            self.playbooks[item["call"]["fn"]].execution_type
                            == PlaybookExecutionType.INT
                        ):
                            abort_execution = True
                            break
                if "updated_vars" in item:
                    updated_variables.update(item["updated_vars"])

        return tool_calls, last_executed_step, updated_variables

    def _prepare_instruction(self) -> str:
        """Prepare the instruction for the current iteration."""
        current_line_number = (
            self.interpreter.call_stack.peek().instruction_pointer.line_number
        )

        return (
            f"\nResume at or after {self.current_playbook.klass}:{current_line_number} based on session log above.\n"
            + self.instruction
        )

    def _get_llm_response(self, instruction: str) -> Generator[str, None, List[str]]:
        """Get response from LLM and process chunks.

        Args:
            instruction: The instruction to send to the LLM.

        Returns:
            A generator that yields chunks and returns the full response.
        """
        prompt = self.interpreter.get_prompt(
            self.playbooks,
            self.current_playbook,
            instruction,
        )
        messages = get_messages_for_prompt(prompt)

        llm_call = LLMCall(
            llm_config=self.llm_config, messages=messages, stream=self.stream
        )
        self.trace(llm_call)

        response = []
        for chunk in llm_call.execute():
            response.append(chunk)
            yield AgentResponseChunk(raw=chunk)
            self.interpreter.process_chunk(chunk)

        # Add a newline chunk for UI formatting, but don't include it in the response
        # This maintains the expected number of chunks for tests
        yield AgentResponseChunk(raw="\n")

        return response

    def _process_tool_calls(
        self, tool_calls: List[ToolCall]
    ) -> Tuple[bool, List[str], bool, List[AgentResponseChunk]]:
        """Process tool calls and determine execution flow.

        Args:
            tool_calls: List of tool calls to process.

        Returns:
            Tuple of (done, playbook_calls, missing_say_after_external_tool_call, response_chunks)
        """
        done = False
        playbook_calls = []
        missing_say_after_external_tool_call = False
        response_chunks = []

        for tool_call in tool_calls:
            if tool_call.fn == "Say":
                if tool_call.kwargs.get("waitForUserInput", False):
                    done = True
                    self.wait_for_external_event = True
                    self.trace(
                        "Waiting for user input, exiting loop",
                        metadata={"tool_call": tool_call},
                    )
                missing_say_after_external_tool_call = False

                response_chunks.append(AgentResponseChunk(tool_call=tool_call))
            elif tool_call.fn not in self.playbooks:
                raise Exception(f"Playbook {tool_call.fn} not found")
            # if tool call is for a playbook, push it to the call stack
            elif (
                self.playbooks[tool_call.fn].execution_type == PlaybookExecutionType.INT
            ):
                playbook_calls.append(tool_call.fn)
                done = True
                self.trace(
                    f"Need to execute playbook: {tool_call.fn}, exiting loop",
                    metadata={"tool_call": tool_call},
                )
            # else pass on the external tool call to agent thread
            else:
                done = True
                # Import here to avoid circular imports
                from .tool_execution import ToolExecution

                tool_execution = ToolExecution(
                    interpreter=self.interpreter,
                    playbooks=self.playbooks,
                    tool_call=tool_call,
                )
                # Collect all chunks from tool execution
                for chunk in tool_execution.execute():
                    response_chunks.append(chunk)
                self.trace(tool_execution)
                self.trace(
                    "Exiting loop after executing tool call",
                    metadata={"tool_call": tool_call},
                )
                missing_say_after_external_tool_call = True

        return (
            done,
            playbook_calls,
            missing_say_after_external_tool_call,
            response_chunks,
        )

    def _update_call_stack(
        self, last_executed_step: str, playbook_calls: List[str]
    ) -> bool:
        """Update call stack based on last executed step and playbook calls.

        Args:
            last_executed_step: The last executed step.
            playbook_calls: List of playbook calls to add to the call stack.

        Returns:
            Boolean indicating if execution should be done.
        """
        (
            last_executed_step_pb,
            last_executed_step_ln,
            last_executed_step_type,
        ) = last_executed_step.split(":")

        done = False
        if last_executed_step_type == "YLD":
            self.wait_for_external_event = True
            done = True
            self.trace(
                "Waiting for external event on YLD, exiting loop",
                metadata={"last_executed_step": last_executed_step},
            )

        # Update call stack to reflect last executed step
        self.interpreter.call_stack.pop()
        self.interpreter.call_stack.push(
            CallStackFrame(
                instruction_pointer=InstructionPointer(
                    playbook=last_executed_step_pb,
                    line_number=last_executed_step_ln,
                ),
                llm_chat_session_id=None,  # self.current_llm_session.llm_chat_session_id,
            )
        )

        # Any requests for playbook execution are pushed to the call stack
        if playbook_calls:
            for playbook_call in playbook_calls:
                self.interpreter.call_stack.push(
                    CallStackFrame(
                        instruction_pointer=InstructionPointer(
                            playbook=playbook_call, line_number="01"
                        ),
                        llm_chat_session_id=None,
                    )
                )
            done = True

        return done

    def execute(self) -> Generator[AgentResponseChunk, None, None]:
        """Execute the interpreter.

        Returns:
            A generator of agent response chunks.
        """
        self.trace(
            "Start execution",
            metadata={
                "instruction": self.instruction,
                "current_playbook": self.current_playbook.klass,
                "session_context": self.interpreter.session_context(),
            },
        )

        done = False
        while not done:
            self.wait_for_external_event = False

            # Prepare instruction for this iteration
            prepared_instruction = self._prepare_instruction()

            self.trace(
                "Start iteration",
                metadata={
                    "playbook": self.current_playbook.klass,
                    "line_number": self.interpreter.call_stack.peek().instruction_pointer.line_number,
                    "instruction": prepared_instruction,
                },
            )

            # Get response from LLM
            response_chunks = []
            raw_response = []
            for chunk in self._get_llm_response(prepared_instruction):
                # Only add to raw_response if it's an actual content chunk, not a formatting newline
                if hasattr(chunk, "raw") and chunk.raw and chunk.raw != "\n":
                    raw_response.append(chunk.raw)
                response_chunks.append(chunk)
                yield chunk

            # Parse the response - use the raw_response list which excludes the newline
            response_text = "".join(raw_response)

            tool_calls, last_executed_step, updated_variables = self.parse_response(
                response_text
            )

            self.trace(
                "LLM execution complete",
                metadata={
                    "tool_calls": tool_calls,
                    "last_executed_step": last_executed_step,
                    "updated_variables": updated_variables,
                },
            )

            # Process tool calls
            self.instruction = ""

            # Process tool calls and determine execution flow
            (
                done,
                playbook_calls,
                missing_say_after_external_tool_call,
                tool_response_chunks,
            ) = self._process_tool_calls(tool_calls)

            # Yield any response chunks from tool calls
            for chunk in tool_response_chunks:
                yield chunk

            # Update variables
            self.interpreter.manage_variables(updated_variables)

            # Update call stack and check if we need to continue execution
            stack_done = self._update_call_stack(last_executed_step, playbook_calls)
            done = done or stack_done

            # If there was no Say() after the last tool call,
            # we need to continue execution after the tool call
            if missing_say_after_external_tool_call:
                self.trace("No Say() after external tool call, continuing loop")
                done = False

    def __repr__(self):
        """Return a string representation of the interpreter execution."""
        # Get list of playbook:line_number pairs from "Start iteration" trace items
        lines = []
        for item in self._trace_items:
            if item.item == "Start iteration":
                lines.append(
                    # item.metadata["playbook"]
                    # + ":"
                    item.metadata["line_number"]
                )
        return ", ".join(lines)
