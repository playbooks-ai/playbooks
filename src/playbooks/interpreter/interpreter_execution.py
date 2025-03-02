"""Interpreter execution module for the interpreter."""

import contextlib
import re
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Tuple

import yaml

from playbooks.call_stack import CallStackFrame, InstructionPointer
from playbooks.llm_call import LLMCall
from playbooks.trace_mixin import TraceMixin
from playbooks.types import AgentResponseChunk, ToolCall
from playbooks.utils.llm_helper import get_messages_for_prompt

if TYPE_CHECKING:
    from playbooks.config import LLMConfig
    from playbooks.playbook import Playbook

    from .interpreter import Interpreter


class ExitCondition:
    """Base class for exit conditions."""

    def check(self, context: Dict[str, Any]) -> Tuple[bool, str, bool]:
        """Check if this exit condition is met.

        Args:
            context: Dictionary containing context for the check

        Returns:
            Tuple of (should_exit, reason, wait_for_external_event)
        """
        raise NotImplementedError


class UserInputExitCondition(ExitCondition):
    """Exit condition for when user input is required."""

    def check(self, context: Dict[str, Any]) -> Tuple[bool, str, bool]:
        """Check if user input is required.

        Args:
            context: Dictionary containing context for the check

        Returns:
            Tuple of (should_exit, reason, wait_for_external_event)
        """
        tool_calls = context.get("tool_calls", [])
        for call in tool_calls:
            if call.wait_for_user_input:
                return (
                    True,
                    "User input requested via Say() with waitForUserInput=True",
                    True,
                )
        return False, None, False


class PlaybookCallExitCondition(ExitCondition):
    """Exit condition for when a playbook call is encountered."""

    def check(self, context: Dict[str, Any]) -> Tuple[bool, str, bool]:
        """Check if a playbook call is encountered.

        Args:
            context: Dictionary containing context for the check

        Returns:
            Tuple of (should_exit, reason, wait_for_external_event)
        """
        tool_calls = context.get("tool_calls", [])
        for call in tool_calls:
            if call.is_internal_playbook_call:
                return True, f"Playbook call to {call.fn}", False
        return False, None, False


class YieldStepExitCondition(ExitCondition):
    """Exit condition for when a YLD step is encountered."""

    def check(self, context: Dict[str, Any]) -> Tuple[bool, str, bool]:
        """Check if a YLD step is encountered.

        Args:
            context: Dictionary containing context for the check

        Returns:
            Tuple of (should_exit, reason, wait_for_external_event)
        """
        tool_calls = context.get("tool_calls", [])
        if not tool_calls:
            return False, None, False

        last_call = tool_calls[-1]
        if last_call.yield_type:
            return True, "YLD step encountered", last_call.yield_type == "ForUserInput"
        return False, None, False


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
        self._trace_items = []
        self.interpreter: "Interpreter" = interpreter
        self.playbooks: Dict[str, "Playbook"] = playbooks
        self.current_playbook: "Playbook" = current_playbook
        self.instruction: str = instruction
        self.llm_config: "LLMConfig" = llm_config
        self.stream: bool = stream

        # Execution state
        self.should_exit = False
        self.exit_reason = None
        self.wait_for_external_event = False
        self.playbook_calls = []
        self.response_chunks = []
        self.missing_say_after_external_tool_call = False

        # Configuration
        self.max_iterations = 10
        self.max_execution_time = 60  # seconds

        # Exit conditions
        self.exit_conditions = [
            UserInputExitCondition(),
            PlaybookCallExitCondition(),
            YieldStepExitCondition(),
        ]

    def parse_response(self, response: str) -> Tuple[List[ToolCall], str, Dict]:
        """Parse the response from the LLM.

        Args:
            response: The response from the LLM.

        Returns:
            A tuple of tool calls, the last executed step, and updated variables.
        """
        # First try to extract yaml content between triple backticks
        yaml_match = re.search(r"```(?:yaml)?(.*?)```", response, re.DOTALL)
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
            from playbooks.interpreter.step_execution import StepExecution

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

                    # if item["call"]["fn"] in self.playbooks:
                    #     # If this is a playbook call, ignore rest of the trace
                    #     # because we will execute the playbook now
                    #     if (
                    #         self.playbooks[item["call"]["fn"]].execution_type
                    #         == PlaybookExecutionType.INT
                    #     ):
                    #         abort_execution = True
                    #         break
                if "updated_vars" in item:
                    updated_variables.update(item["updated_vars"])

        return tool_calls, last_executed_step, updated_variables

    def _prepare_instruction(self) -> str:
        """Prepare the instruction for the current iteration."""
        # Check if call stack is empty
        if self.interpreter.call_stack.is_empty():
            # If call stack is empty, we're at the end of execution
            return (
                f"Playbook {self.current_playbook.klass} execution has completed.\n"
                + self.instruction
            )

        current_line_number = self.interpreter.get_current_line_number()

        return (
            f"Continue playbook {self.current_playbook.klass} execution from line {current_line_number}.\n"
            + self.instruction
        )

    def _get_llm_response(
        self, instruction: str
    ) -> Generator[AgentResponseChunk, None, None]:
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

    def _annotate_tool_calls(self, tool_calls: List[ToolCall]) -> List[ToolCall]:
        """Annotate tool calls with additional information.

        Args:
            tool_calls: List of tool calls to annotate

        Returns:
            List of annotated tool calls
        """
        for call in tool_calls:
            call.annotate(self.playbooks)
        return tool_calls

    def _check_exit_conditions(self, context: Dict[str, Any]) -> bool:
        """Check all exit conditions.

        Args:
            context: Dictionary containing context for the check

        Returns:
            True if any exit condition is met, False otherwise
        """
        # First check if we're already in an exit state
        if self.should_exit:
            return True

        # Check other exit conditions
        for condition in self.exit_conditions:
            should_exit, reason, wait_for_external = condition.check(context)
            if should_exit:
                self.should_exit = True
                self.exit_reason = reason
                self.wait_for_external_event |= wait_for_external
                self.trace(f"Exit condition met: {reason}")
                return True
        return False

    def _process_tool_calls(self, tool_calls: List[ToolCall]) -> None:
        """Process tool calls and update execution state.

        Args:
            tool_calls: List of tool calls to process
        """
        # Reset state
        self.playbook_calls = []
        self.response_chunks = []
        has_external_tool_call = False
        has_say_call = False

        # Process each call
        for call in tool_calls:
            if call.is_say:
                has_say_call = True
                self.response_chunks.append(AgentResponseChunk(tool_call=call))
            elif call.is_internal_playbook_call:
                self.playbook_calls.append(call.fn)
            elif call.fn not in self.playbooks:
                # External tool call
                has_external_tool_call = True
                # Import here to avoid circular imports
                from playbooks.interpreter.tool_execution import ToolExecution

                tool_execution = ToolExecution(
                    interpreter=self.interpreter,
                    playbooks=self.playbooks,
                    tool_call=call,
                )
                # Collect all chunks from tool execution
                for chunk in tool_execution.execute():
                    self.response_chunks.append(chunk)
                self.trace(tool_execution)

        # Check if we need to continue after external tool call
        if has_external_tool_call and not has_say_call:
            self.missing_say_after_external_tool_call = True
            self.trace(
                "External tool call without Say(), may need to continue execution"
            )

        # If only Say calls and no external tools or playbooks, we should wait for user input
        if has_say_call and not has_external_tool_call and not self.playbook_calls:
            self.wait_for_external_event = True
            self.should_exit = True
            self.exit_reason = "Only Say() calls found, waiting for user input"
            self.trace(self.exit_reason)

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

        self.trace(
            f"Updating call stack for {last_executed_step}",
            metadata={
                "call_stack_before": self.interpreter.call_stack.to_dict(),
                "playbook_calls": playbook_calls,
            },
        )

        # Update call stack to reflect last executed step
        self.interpreter.call_stack.pop()

        # If the last executed line is RET, we should pop the stack and not push a new frame
        if last_executed_step_type == "RET":
            # The frame was already popped above, no need to push a new one
            self.trace(
                f"Processed RET instruction from {last_executed_step_pb}",
                metadata={
                    "call_stack_after_pop": self.interpreter.call_stack.to_dict(),
                },
            )

            # Check if the call stack is now empty after popping the RET instruction
            should_exit, exit_reason = self.interpreter.handle_empty_call_stack(
                {"playbook": self.current_playbook.klass}
            )
            if should_exit:
                self.should_exit = should_exit
                self.exit_reason = exit_reason
                return True

            # If we're returning from a playbook call and there's still a frame in the call stack,
            # we should continue execution from that frame instead of exiting
            if (
                self.current_playbook.klass
                != self.interpreter.get_current_playbook_name()
            ):
                self.trace(
                    f"Returning from {self.current_playbook.klass} to {self.interpreter.get_current_playbook_name()}",
                    metadata={
                        "call_stack": self.interpreter.call_stack.to_dict(),
                    },
                )
                # Don't set should_exit to True, as we want to continue execution
                return False
        else:
            # Check if the playbook has a step collection
            if (
                hasattr(self.current_playbook, "step_collection")
                and self.current_playbook.step_collection
            ):
                # For all non-RET instructions, find the next step and push it to the stack
                current_step = self.current_playbook.get_step(last_executed_step_ln)
                if current_step:
                    next_step = self.current_playbook.get_next_step(
                        last_executed_step_ln
                    )

                    if next_step:
                        # We found a next step, push it to the call stack
                        self.interpreter.call_stack.push(
                            CallStackFrame(
                                instruction_pointer=InstructionPointer(
                                    playbook=last_executed_step_pb,
                                    line_number=next_step.line_number,
                                ),
                                llm_chat_session_id=None,
                            )
                        )
                        self.trace(
                            f"Advanced from line {last_executed_step_ln} to line {next_step.line_number}"
                        )

                        # Log if the next step is a RET
                        if next_step.is_return():
                            self.trace("Next line is RET, advancing to it")
                    else:
                        # No next step found, this is the last line in the playbook
                        self.trace(
                            "Last line of playbook reached, not pushing new frame"
                        )
                        # We've already popped once above, so no need to pop again
                        # Just return without pushing a new frame
                        return False
                else:
                    # Fallback if we can't find the step
                    self.trace(
                        f"Could not find step at line {last_executed_step_ln}, using original behavior"
                    )
                    # Push the same line number back onto the stack
                    self.interpreter.call_stack.push(
                        CallStackFrame(
                            instruction_pointer=InstructionPointer(
                                playbook=last_executed_step_pb,
                                line_number=last_executed_step_ln,
                            ),
                            llm_chat_session_id=None,
                        )
                    )
            else:
                # No step collection available, use original behavior
                self.trace("No step collection available, using original behavior")
                # For YLD instructions, we need to advance to the next line to prevent infinite loops
                if last_executed_step_type == "YLD":
                    # Try to determine if this is the last line in the playbook
                    # This is a heuristic since we don't have the step collection
                    try:
                        # Check if there's a next line in the playbook
                        if "." in last_executed_step_ln:
                            # For nested line numbers like "01.01"
                            parent_line, sub_line = last_executed_step_ln.split(".")
                            next_line = f"{parent_line}.{int(sub_line) + 1:02d}"
                        else:
                            # For simple line numbers like "01"
                            next_line = f"{int(last_executed_step_ln) + 1:02d}"

                        # Check if the next line exists in the playbook
                        # Since we don't have the step collection, we'll use a heuristic
                        # If the line number is high (e.g., > 10), assume it's the last line
                        if "." in last_executed_step_ln:
                            parent_line, sub_line = last_executed_step_ln.split(".")
                            if int(sub_line) > 10:
                                self.trace(
                                    f"Assuming YLD at line {last_executed_step_ln} is the last line"
                                )
                                return False
                        else:
                            if int(last_executed_step_ln) > 10:
                                self.trace(
                                    f"Assuming YLD at line {last_executed_step_ln} is the last line"
                                )
                                return False

                        self.trace(
                            f"Advanced from YLD at line {last_executed_step_ln} to line {next_line}"
                        )

                        # Push the next line onto the stack
                        self.interpreter.call_stack.push(
                            CallStackFrame(
                                instruction_pointer=InstructionPointer(
                                    playbook=last_executed_step_pb,
                                    line_number=next_line,
                                ),
                                llm_chat_session_id=None,
                            )
                        )
                    except Exception as e:
                        self.trace(
                            f"Error calculating next line number: {e}, using same line"
                        )
                        # If we can't calculate the next line, use the same line
                        self.interpreter.call_stack.push(
                            CallStackFrame(
                                instruction_pointer=InstructionPointer(
                                    playbook=last_executed_step_pb,
                                    line_number=last_executed_step_ln,
                                ),
                                llm_chat_session_id=None,
                            )
                        )
                else:
                    # For non-YLD, non-RET instructions, push the updated frame with the same line number
                    self.interpreter.call_stack.push(
                        CallStackFrame(
                            instruction_pointer=InstructionPointer(
                                playbook=last_executed_step_pb,
                                line_number=last_executed_step_ln,
                            ),
                            llm_chat_session_id=None,
                        )
                    )

        # Any requests for playbook execution are pushed to the call stack
        retval = False
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
            retval = True

        self.interpreter.trace(self.interpreter.call_stack.to_trace_item())
        return retval

    def _compute_state_hash(self) -> int:
        """Compute a hash of the current execution state to detect lack of progress."""
        state = {
            "call_stack": str(self.interpreter.call_stack.to_dict()),
            "variables": str(self.interpreter.local_variables.to_dict()),
            "line_number": self.interpreter.get_current_line_number(),
        }
        return hash(str(state))

    def execution_loop(self):
        """Context manager for the execution loop that ensures proper cleanup."""

        @contextlib.contextmanager
        def _execution_loop():
            should_continue = True

            def check_continue():
                return should_continue

            try:
                yield check_continue
            finally:
                should_continue = False

        return _execution_loop()

    def execute(self) -> Generator[AgentResponseChunk, None, None]:
        """Execute the interpreter.

        Returns:
            A generator of agent response chunks.
        """
        with self.execution_loop() as should_continue:
            while should_continue():
                # Reset state for this iteration
                self.wait_for_external_event = False

                # Prepare instruction for this iteration
                prepared_instruction = self._prepare_instruction()

                # Check if call stack is empty
                should_exit, exit_reason = self.interpreter.handle_empty_call_stack(
                    {"playbook": self.current_playbook.klass}
                )
                if should_exit:
                    self.should_exit = should_exit
                    self.exit_reason = exit_reason
                    break

                # Get the current frame (we know it exists because handle_empty_call_stack didn't exit)
                current_frame = self.interpreter.call_stack.peek()

                # Check if we need to switch to a different playbook
                current_playbook_in_stack = self.interpreter.get_current_playbook_name()
                if current_playbook_in_stack != self.current_playbook.klass:
                    self.trace(
                        f"Current playbook {self.current_playbook.klass} doesn't match stack playbook {current_playbook_in_stack}, exiting to switch"
                    )
                    self.should_exit = True
                    self.exit_reason = (
                        f"Switching to playbook {current_playbook_in_stack}"
                    )
                    break

                self.trace(
                    "Start inner loop iteration",
                    metadata={
                        "playbook": self.current_playbook.klass,
                        "line_number": current_frame.instruction_pointer.line_number,
                        "instruction": prepared_instruction,
                    },
                )

                # Get response from LLM
                raw_response = []
                for chunk in self._get_llm_response(prepared_instruction):
                    # Only add to raw_response if it's an actual content chunk
                    if hasattr(chunk, "raw") and chunk.raw:
                        raw_response.append(chunk.raw)
                    yield chunk

                # Parse the response - use the raw_response list which excludes the newline
                response_text = "".join(raw_response)

                tool_calls, last_executed_step, updated_variables = self.parse_response(
                    response_text
                )

                self.trace(
                    "LLM response parsed",
                    metadata={
                        "tool_calls": tool_calls,
                        "last_executed_step": last_executed_step,
                        "updated_variables": updated_variables,
                    },
                )

                # Annotate and process tool calls
                tool_calls = self._annotate_tool_calls(tool_calls)
                self._process_tool_calls(tool_calls)

                # Yield any response chunks from tool processing
                for chunk in self.response_chunks:
                    yield chunk

                # Update variables
                self.interpreter.manage_variables(updated_variables)

                # Update call stack and check if we need to continue execution
                stack_exit = self._update_call_stack(
                    last_executed_step, self.playbook_calls
                )
                if stack_exit and not self.should_exit:
                    self.should_exit = True
                    self.exit_reason = "Call stack update required exit"

                # If there was no Say() after the last tool call,
                # we need to continue execution after the tool call
                if self.missing_say_after_external_tool_call and not self.should_exit:
                    self.trace("No Say() after external tool call, continuing loop")
                    self.should_exit = False

                # Check if we need to switch to a different playbook after updating the call stack
                current_playbook_in_stack = self.interpreter.get_current_playbook_name()
                if current_playbook_in_stack != self.current_playbook.klass:
                    self.trace(
                        f"After call stack update, current playbook {self.current_playbook.klass} doesn't match stack playbook {current_playbook_in_stack}, exiting to switch",
                        metadata={
                            "call_stack": self.interpreter.call_stack.to_dict(),
                            "last_executed_step": last_executed_step,
                            "last_executed_step_type": last_executed_step.split(":")[
                                -1
                            ],
                        },
                    )
                    self.should_exit = True
                    self.exit_reason = (
                        f"Switching to playbook {current_playbook_in_stack}"
                    )
                    break

                # Check exit conditions
                context = {
                    "tool_calls": tool_calls,
                    "last_executed_step": last_executed_step,
                    "response_text": response_text,
                }
                if self._check_exit_conditions(context):
                    break
                else:
                    # Add a trace indicating why we are continuing the loop
                    self.trace(
                        "Continue inner loop iteration",
                        metadata={
                            "reason": "No exit conditions met, continuing execution",
                            "current_playbook": self.current_playbook.klass,
                            "current_line": self.interpreter.get_current_line_number(),
                            "has_tool_calls": bool(tool_calls),
                            "has_playbook_calls": bool(self.playbook_calls),
                            "missing_say_after_tool": self.missing_say_after_external_tool_call,
                            "variables_updated": bool(updated_variables),
                        },
                    )

    def __repr__(self):
        """Return a string representation of the interpreter execution."""
        # Get list of playbook:line_number pairs from "Start iteration" trace items
        lines = []
        for item in self._trace_items:
            if item.item == "Start inner loop iteration":
                lines.append(
                    self.current_playbook.klass + ":" + item.metadata["line_number"]
                )
        return ", ".join(lines)
