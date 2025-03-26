"""Interpreter execution module for executing playbooks."""

import json
import re
import time
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Tuple

from playbooks.call_stack import CallStackFrame, InstructionPointer
from playbooks.interpreter.execution_state import ExecutionState
from playbooks.interpreter.exit_conditions import (
    EmptyCallStackExitCondition,
    ExitCondition,
    MaxExecutionTimeExitCondition,
    MaxIterationsExitCondition,
    NoProgressExitCondition,
    PlaybookCallExitCondition,
    PlaybookSwitchExitCondition,
    ReturnFromPlaybookExitCondition,
    SayOnlyExitCondition,
    UserInputRequiredExitCondition,
    YieldStepExitCondition,
)
from playbooks.interpreter.interpreter_prompt import InterpreterPrompt
from playbooks.interpreter.output_item import OutputItem
from playbooks.llm_call import LLMCall
from playbooks.playbook import Playbook
from playbooks.trace_mixin import TraceMixin
from playbooks.types import AgentResponseChunk, ToolCall

if TYPE_CHECKING:
    from playbooks.config import LLMConfig


class InterpreterLoopExitConditions(TraceMixin):
    """Class for managing interpreter loop exit conditions."""

    def __init__(self, state: ExecutionState, current_playbook_klass: str | None):
        """Initialize the interpreter loop exit conditions.

        Args:
            state: The execution state
            current_playbook_klass: The current playbook class name, or None.
        """
        super().__init__()
        self.state = state
        self.current_playbook_klass = current_playbook_klass

        # Initialize exit conditions
        self.user_input_required_condition = UserInputRequiredExitCondition()
        self.playbook_call_condition = PlaybookCallExitCondition()
        self.yield_step_condition = YieldStepExitCondition()
        self.empty_call_stack_condition = EmptyCallStackExitCondition()
        self.playbook_switch_condition = PlaybookSwitchExitCondition()
        self.return_from_playbook_condition = ReturnFromPlaybookExitCondition()
        self.say_only_condition = SayOnlyExitCondition()
        self.max_iterations_condition = MaxIterationsExitCondition(
            self.state.max_iterations
        )
        self.max_execution_time_condition = MaxExecutionTimeExitCondition(
            self.state.max_execution_time
        )
        self.no_progress_condition = NoProgressExitCondition(state=self.state)

        # Initialize context
        self.iteration_count = 0
        self.start_time = time.monotonic()

    def should_continue(self) -> bool:
        """Check if the interpreter loop should continue executing.

        Returns:
            True if the loop should continue, False otherwise.
        """
        # Increment iteration count
        self.iteration_count += 1

        # --- Immediate exit checks based on state changes from the last response processing ---

        # If an external tool was called without a subsequent Say(), pause execution.
        if self.state.missing_say_after_external_tool_call:
            self.trace(
                "Pausing loop: External tool call occurred without a following Say()."
            )
            return False

        # If an internal playbook call was requested, exit the loop to handle it.
        if len(self.state.playbook_calls) > 0:
            self.trace("Exiting loop: Internal playbook call detected.")
            return False

        # If the state indicates waiting for an external event (e.g., user input after Say()), exit.
        if self.state.wait_for_external_event:
            self.trace(
                f"Exiting loop: Waiting for external event: {self.state.exit_reason}"
            )
            return False

        # Check exit conditions
        conditions: List[Tuple[ExitCondition, List[Any]]] = [
            [self.user_input_required_condition, [self.state]],
            [self.playbook_call_condition, [self.state]],
            [self.yield_step_condition, [self.state]],
            [self.empty_call_stack_condition, [self.state.call_stack]],
            [self.playbook_switch_condition, [self.state, self.current_playbook_klass]],
            [self.return_from_playbook_condition, [self.state]],
            [self.say_only_condition, [self.state]],
            [self.max_iterations_condition, [self.iteration_count]],
            [self.max_execution_time_condition, []],
            [self.no_progress_condition, [self.state]],
        ]

        for condition, args in conditions:
            if condition.check(*args):
                self.trace(f"{condition.reason}, exiting interpreter execution loop")
                self.exit_condition_reason = condition.reason
                return False

        self.trace("No exit conditions met, continuing interpreter execution loop.")
        return True


class InterpreterExecution(TraceMixin):
    """Represents one execution cycle of the interpreter loop."""

    def __init__(
        self,
        state: ExecutionState,
        current_playbook: Playbook | None,
    ):
        """Initialize an interpreter execution cycle.

        Args:
            state: The current execution state.
            current_playbook: The current playbook being executed (can be None if stack is empty).
        """
        super().__init__()
        self.state: ExecutionState = state
        self.current_playbook: Playbook | None = current_playbook

    def execute(
        self,
        playbooks: Dict[str, "Playbook"],
        instruction: str,
        llm_config: "LLMConfig",
        stream: bool,
    ) -> Generator[AgentResponseChunk, None, None]:
        """Execute the interpreter loop until an exit condition is met.

        Args:
            playbooks: The available playbooks.
            instruction: The initial instruction or tool results to process.
            llm_config: The LLM configuration.
            stream: Whether to stream the response.

        Yields:
            AgentResponseChunk: Chunks of the agent's response (e.g., LLM output, tool calls).
        """
        done = False
        current_instruction = instruction  # Start with the initial instruction

        while not done:
            # Get the LLM response based on the current state and instruction
            raw_response = []
            for chunk in self._get_llm_response(
                playbooks=playbooks,
                instruction=current_instruction,
                llm_config=llm_config,
                stream=stream,
            ):
                raw_response.append(chunk.raw) if chunk.raw else None
                yield chunk

            # Process the response, update state (tool calls, vars, call stack), and yield results
            yield from self._process_response_and_update_state(
                playbooks=playbooks, raw_response=raw_response
            )

            # Check exit conditions after processing the response
            exit_conditions = InterpreterLoopExitConditions(
                state=self.state,
                current_playbook_klass=(
                    self.current_playbook.klass if self.current_playbook else None
                ),
            )
            self.trace(exit_conditions)  # Trace the exit condition checker itself

            done = not exit_conditions.should_continue()

            # If not done, prepare instruction for the next iteration (tool results)
            if not done:
                tool_results = [
                    tool_execution.result.to_trace()
                    for tool_execution in self.state.tool_executions
                ]
                current_instruction = "\n".join(tool_results)
                # Clear tool executions now that they've been consumed
                self.state.tool_executions.clear()

    def _get_llm_response(
        self,
        playbooks: Dict[str, "Playbook"],
        instruction: str,
        llm_config: "LLMConfig",
        stream: bool,
    ) -> Generator[AgentResponseChunk, None, None]:
        """Get response from LLM based on the current state and instruction.

        Yields:
            AgentResponseChunk: Chunks from the LLM call.
        """
        # Get the instruction indicating the current execution point
        execution_instruction = self._prepare_execution_instruction()

        # Combine execution point instruction with the current input/tool results
        full_instruction = f"{execution_instruction}\n{instruction}".strip()

        # Get the prompt
        prompt = InterpreterPrompt(
            state=self.state,
            playbooks=playbooks,
            current_playbook=self.current_playbook,
            instruction=full_instruction,
            agent_instructions=self.state.agent.description,
        )

        # Create LLM call
        llm_call = LLMCall(
            llm_config=llm_config,
            messages=prompt.messages,
            stream=stream,
            json_mode=False,  # interpreter calls produce markdown
            session_id=self.state.agent_thread.id,
        )

        # Execute LLM call and yield chunks
        self.trace(llm_call)
        yield from llm_call.execute()
        yield AgentResponseChunk(raw="\n")  # Ensure separation for markdown blocks

    def _prepare_execution_instruction(self) -> str:
        """Prepare the instruction part indicating the current execution point for the LLM.

        Returns:
            A string like "Continue execution from PlaybookName:LineNumber".
        """
        current_frame = self.state.call_stack.peek()

        if current_frame:
            playbook = current_frame.instruction_pointer.playbook
            line_number = current_frame.instruction_pointer.line_number
            return f"Continue execution from {playbook}:{line_number}"
        else:
            # If the call stack is empty, execution starts implicitly
            return ""

    def _process_response_and_update_state(
        self, playbooks: Dict[str, "Playbook"], raw_response: List[str]
    ) -> Generator[AgentResponseChunk, None, None]:
        """Parse the LLM response, update state, and process tool calls.

        Args:
            playbooks: Dictionary of available playbooks.
            raw_response: The raw response chunks from the LLM.

        Yields:
            AgentResponseChunk: Chunks generated during tool processing (e.g., Say calls).
        """
        response_text = "".join(raw_response)

        # Parse the response into structured data
        (
            tool_calls,
            last_executed_step,
            updated_variables,
            updated_call_stack,
        ) = self.parse_response(response_text)

        # Update state based on parsed data
        self.state.tool_calls = tool_calls  # Store raw tool calls from LLM
        self.state.last_executed_step = last_executed_step
        self.state.update_variables(updated_variables)
        self._update_call_stack(
            updated_call_stack
        )  # Updates based on LLM suggestion and last_executed_step

        # Annotate tool calls with type information (e.g., internal, external, say)
        for call in tool_calls:
            call.annotate(playbooks)  # Modifies call object in-place

        # Process the annotated tool calls (execute external, handle internal/say)
        # This also updates self.state (e.g., playbook_calls, tool_executions, conversation_history)
        yield from self._process_tool_calls(tool_calls=tool_calls)

        # Note: self.state.tool_executions now holds results of *external* calls executed above.
        # These results will be used as input for the *next* LLM call in the main execute loop.

    # ================================

    def get_trace_metadata(self) -> Dict[str, Any]:
        """Get metadata for tracing this execution step."""
        return {
            "current_playbook": (
                self.current_playbook.klass if self.current_playbook else None
            ),
            # 'instruction' is passed to execute, not stored as instance var
            "call_stack": self.state.call_stack.to_dict(),
        }

    def parse_response(
        self, response: str
    ) -> Tuple[List[ToolCall], str | None, Dict, List[str] | None]:
        """Parse the response from the LLM (expecting markdown format primarily).

        Args:
            response: The raw response string from the LLM.

        Returns:
            A tuple containing:
                - List of parsed ToolCall objects.
                - The last executed step string (e.g., "Playbook:01:CMD"), or None.
                - Dictionary of updated variables.
                - List representing the updated call stack (if provided by LLM), or None.
        """
        if not response:
            self.trace("Received empty response", level="WARNING")
            return [], None, {}, None

        try:
            # Try to extract markdown bullet points first
            bullet_points = self._extract_markdown_bullet_points(response)

            if not bullet_points:
                # Fall back to the old JSON format if markdown format is not found
                self.trace(
                    "No markdown content found or extracted, falling back to JSON format"
                )
                # JSON format doesn't include call stack updates
                tool_calls, last_step, updated_vars = self._parse_json_response(
                    response
                )
                return tool_calls, last_step, updated_vars, None

            # Parse each bullet point into an OutputItem
            output_items = [OutputItem(point) for point in bullet_points]

            # Extract tool calls, last executed step, updated variables, and call stack
            tool_calls = []
            last_executed_step = None
            updated_variables = {}
            updated_call_stack = None

            for item in output_items:
                # Extract tool calls
                for tool_call_data in item.tool_calls:
                    tool_calls.append(
                        ToolCall(
                            fn=tool_call_data["function_name"],
                            args=tool_call_data.get("args", []),
                            kwargs=tool_call_data.get("kwargs", {}),
                        )
                    )

                # Use the last step found across all items
                if item.steps:
                    last_executed_step = item.steps[-1]

                # Extract updated variables (merge dictionaries)
                for var_name, var_value in item.vars:
                    updated_variables[var_name] = var_value

                # Use the call stack if provided (assuming only one update)
                if item.call_stack:
                    updated_call_stack = item.call_stack

            return tool_calls, last_executed_step, updated_variables, updated_call_stack

        except Exception as e:
            self.trace(
                f"Error parsing response: {str(e)}",
                level="ERROR",
                metadata={"response": response},
            )
            return [], None, {}, None

    def _extract_markdown_bullet_points(self, response: str) -> List[str]:
        """Extract content of markdown bullet points (lines starting with '- ').

        Tries to find them within ```md ... ``` blocks first, then ``` ... ```,
        then anywhere in the response.

        Args:
            response: The response string from the LLM.

        Returns:
            A list of bullet point content strings, or an empty list if none found.
        """
        # 1. Look inside ```md ... ```
        md_match = re.search(r"```md\s*(.*?)\s*```", response, re.DOTALL)
        if md_match:
            md_content = md_match.group(1)
            bullet_points = [
                line.strip()[2:].strip()
                for line in md_content.split("\n")
                if line.strip().startswith("- ")
            ]
            if bullet_points:
                return bullet_points

        # 2. Look inside ``` ... ``` (generic code block)
        code_match = re.search(r"```\s*(.*?)\s*```", response, re.DOTALL)
        if code_match:
            code_content = code_match.group(1)
            bullet_points = [
                line.strip()[2:].strip()
                for line in code_content.split("\n")
                if line.strip().startswith("- ")
            ]
            if bullet_points:
                return bullet_points

        # 3. Look anywhere in the response
        bullet_points = [
            line.strip()[2:].strip()
            for line in response.split("\n")
            if line.strip().startswith("- ")
        ]
        return bullet_points

    def _parse_json_response(
        self, response: str
    ) -> Tuple[List[ToolCall], str | None, Dict]:
        """Parse the response from the LLM assuming the legacy JSON format.

        Args:
            response: The response string from the LLM.

        Returns:
            A tuple of tool calls, the last executed step string, and updated variables.
        """
        json_content = response  # Default to using the whole response
        try:
            # Try to extract json content between triple backticks first
            json_match = re.search(r"```(?:json)?\s*(.*?)\s*```", response, re.DOTALL)
            if json_match:
                json_content = json_match.group(1)
                self.trace(
                    "Found JSON content in triple backticks for fallback parsing"
                )
            else:
                self.trace(
                    "No triple backticks found, attempting to parse entire response as JSON"
                )

            # Parse the JSON content
            parsed = json.loads(json_content)
            if not isinstance(parsed, dict):
                raise ValueError("Parsed JSON is not a dictionary")

            # Extract tool calls
            tool_calls = []
            for tool_call in parsed.get("tool_calls", []):
                if isinstance(tool_call, dict) and "function_name" in tool_call:
                    tool_calls.append(
                        ToolCall(
                            fn=tool_call["function_name"],
                            args=tool_call.get("args", []),
                            kwargs=tool_call.get("kwargs", {}),
                        )
                    )
                else:
                    self.trace(
                        f"Skipping invalid tool call item in JSON: {tool_call}",
                        level="WARNING",
                    )

            # Extract last executed step
            last_executed_step = parsed.get("last_executed_step")
            if last_executed_step and not isinstance(last_executed_step, str):
                self.trace(
                    f"Invalid 'last_executed_step' format in JSON: {last_executed_step}",
                    level="WARNING",
                )
                last_executed_step = None

            # Extract updated variables
            updated_variables = parsed.get("updated_variables", {})
            if not isinstance(updated_variables, dict):
                self.trace(
                    f"Invalid 'updated_variables' format in JSON: {updated_variables}",
                    level="WARNING",
                )
                updated_variables = {}

            return tool_calls, last_executed_step, updated_variables

        except Exception as e:
            self.trace(
                f"Error parsing fallback JSON response: {str(e)}",
                level="ERROR",
                metadata={"response_attempted": json_content},
            )
            return [], None, {}

    def _process_tool_calls(
        self, tool_calls: List[ToolCall]
    ) -> Generator[AgentResponseChunk, None, None]:
        """Process annotated tool calls: execute external, handle internal/say, update state.

        Args:
            tool_calls: List of annotated tool calls to process.

        Yields:
            AgentResponseChunk: Yields chunks for Say calls.
        """
        # Reset state related to tool call processing for this turn
        self.state.clear_tool_calls()  # Clear raw tool calls from state (already processed)
        self.state.clear_playbook_calls()  # Clear internal playbook calls from previous turn
        self.state.clear_response_chunks()  # Clear any leftover chunks
        self.state.missing_say_after_external_tool_call = False  # Reset flag

        has_external_tool_call = False
        has_say_call = False

        # Process each call based on its annotated type
        for call in tool_calls:
            if call.is_say:
                has_say_call = True
                # Yield the Say call as a chunk for the caller to handle
                yield AgentResponseChunk(tool_call=call)
                # Add Say content to conversation history
                say_content = call.args[0] if call.args else ""
                self.state.add_conversation_history(
                    f"{self.state.agent.klass}: {say_content}"
                )
            elif call.is_internal_playbook_call:
                # Mark the internal playbook call to be handled by the main loop/caller
                self.state.add_playbook_call(call.fn)
                self.trace(f"Detected internal playbook call to: {call.fn}")
                # Stop processing further calls in this batch if an internal call is found
                break
            elif call.is_external_playbook_call:
                has_external_tool_call = True
                # Import here to avoid circular imports
                from playbooks.interpreter.tool_execution import ToolExecution
                from playbooks.playbook_library import (
                    PlaybookLibrary,  # Assuming this exists
                )

                tool_execution = ToolExecution(tool_call=call)

                # Find the actual playbook function to execute
                # TODO: Refactor playbook loading/access if PlaybookLibrary changes
                playbook_instance = PlaybookLibrary.get_playbook_instance(
                    call.fn
                )  # Example access

                if (
                    not playbook_instance
                    or not hasattr(playbook_instance, "func")
                    or not callable(playbook_instance.func)
                ):
                    self.trace(
                        f"External playbook/function '{call.fn}' not found or not callable, skipping execution.",
                        level="WARNING",
                    )
                    # Create a failed execution result
                    tool_execution.result.set_error(
                        f"Playbook/function '{call.fn}' not found or not callable."
                    )
                else:
                    try:
                        # Execute the external playbook function
                        tool_execution.execute(playbook_instance.func)
                    except Exception as e:
                        self.trace(
                            f"Error executing external tool {call.fn}: {e}",
                            level="ERROR",
                        )
                        tool_execution.result.set_error(str(e))

                # Store the execution result (success or failure)
                self.state.tool_executions.append(tool_execution)
                # Add tool execution trace to conversation history
                self.state.add_conversation_history(tool_execution.__repr__())
                self.trace(tool_execution)  # Trace the ToolExecution object itself
            else:
                # This might happen if annotation failed or a new type was added
                self.trace(
                    f"Skipping tool call with unhandled type: {call.fn}",
                    level="WARNING",
                )

        # --- Post-processing checks ---

        # Check if an external tool was called but no Say() followed in the same turn
        if has_external_tool_call and not has_say_call:
            self.state.missing_say_after_external_tool_call = True
            self.trace(
                "External tool call(s) executed without a subsequent Say(). Flag set."
            )

        # If only Say calls were made (no external tools, no internal calls),
        # set state to wait for user input.
        if (
            has_say_call
            and not has_external_tool_call
            and not self.state.playbook_calls  # Check if an internal call was triggered
        ):
            self.state.wait_for_external_event = True
            self.state.should_exit = True  # Indicate interpreter should yield control
            reason = "Only Say() calls processed, waiting for user input."
            self.state.exit_reason = reason
            self.trace(reason)

    def _update_call_stack(self, updated_call_stack: List[str] | None) -> None:
        """Update the call stack based on LLM suggestion, last executed step, and internal calls.

        Order of operations:
        1. Apply LLM's suggested call stack if provided.
        2. Update based on `last_executed_step` (pop current, push next/same).
        3. Push frames for any detected internal `playbook_calls`.

        Args:
            updated_call_stack: The call stack structure suggested by the LLM, or None.
        """
        call_stack_before_str = repr(self.state.call_stack)

        # 1. Apply LLM suggestion (if any)
        if updated_call_stack:
            self.trace(f"LLM suggested call stack update: {updated_call_stack}")
            try:
                self.state.set_call_stack(updated_call_stack)
                self.trace("Applied LLM suggested call stack.")
                # If LLM updated it, skip step-based update for this turn?
                # For now, let's proceed, step update might refine it.
            except Exception as e:
                self.trace(
                    f"Error applying LLM suggested call stack: {e}", level="ERROR"
                )

        # 2. Update call stack based on last executed step (if available)
        if self.state.last_executed_step:
            self._update_call_stack_from_step(self.state.last_executed_step)
        else:
            self.trace(
                "No 'last_executed_step' provided by LLM, skipping step-based call stack update."
            )

        # 3. Push frames for newly requested internal playbook calls
        # These calls were identified in _process_tool_calls
        for playbook_call_name in self.state.playbook_calls:
            self.trace(f"Pushing new frame for internal call to: {playbook_call_name}")
            self.state.call_stack.push(
                CallStackFrame(
                    instruction_pointer=InstructionPointer(
                        playbook=playbook_call_name,
                        line_number="01",  # Assume starting at line 01
                    ),
                    llm_chat_session_id=None,  # Or manage session ID if needed
                )
            )

        call_stack_after_str = repr(self.state.call_stack)
        if call_stack_before_str != call_stack_after_str:
            self.trace(
                f"Call stack updated: {call_stack_after_str}",
                metadata={
                    "before": call_stack_before_str,
                    "after": call_stack_after_str,
                },
            )
        else:
            self.trace("Call stack remains unchanged.")

    def _update_call_stack_from_step(self, last_executed_step: str) -> None:
        """Update call stack based on the last executed step reported by the LLM.

        Pops the current frame and pushes the next logical frame based on the step type
        and playbook structure (if available).

        Args:
            last_executed_step: The step string (e.g., "Playbook:01:CMD").
        """
        # Parse the step string
        parts = last_executed_step.split(":")
        if len(parts) != 3:
            self.trace(
                f"Invalid last_executed_step format: '{last_executed_step}'. Cannot update call stack from step.",
                level="WARNING",
                metadata={"expected_format": "playbook:line_number:type"},
            )
            return

        pb_name, ln_str, step_type = parts
        update_message = f"Processing step {last_executed_step}: "

        # Pop the frame corresponding to the step that was just executed
        popped_frame = self.state.call_stack.pop()
        if not popped_frame:
            self.trace(
                f"{update_message}Cannot pop frame, stack is empty.", level="WARNING"
            )
            return  # Should not happen if last_executed_step is valid

        self.trace(
            f"{update_message}Popped frame for {popped_frame.instruction_pointer}"
        )

        # Handle RET (Return) instruction: Just pop, don't push anything new.
        if step_type == "RET":
            update_message += f"Processed RET from {pb_name}. "
            if self.state.call_stack.is_empty():
                # This signals the end of the main playbook or a sub-playbook call returning
                self.state.request_exit("Call stack empty after RET", False)
                update_message += "Call stack is now empty."
            else:
                next_frame = self.state.call_stack.peek()
                update_message += f"Returning to {next_frame.instruction_pointer}."
            self.trace(update_message)
            return  # Done processing RET

        # Handle non-RET instructions: Determine the next step to push.

        next_step_ip: InstructionPointer | None = None

        # Try using StepCollection for accurate next step
        if (
            self.current_playbook  # Ensure we have a current playbook context
            and self.current_playbook.klass
            == pb_name  # Ensure it matches the step's playbook
            and hasattr(self.current_playbook, "step_collection")
            and self.current_playbook.step_collection
        ):
            next_step_obj = self.current_playbook.get_next_step(ln_str)
            if next_step_obj:
                next_step_ip = InstructionPointer(
                    playbook=pb_name, line_number=next_step_obj.line_number
                )
                update_message += (
                    f"Found next step {next_step_ip.line_number} using StepCollection. "
                )
            else:
                # Reached the end of the playbook according to StepCollection
                update_message += (
                    "Reached end of playbook (no next step in StepCollection). "
                )
                # Don't push a new frame, effectively popping the last line.
        else:
            # Fallback: No StepCollection or playbook mismatch, use heuristics
            update_message += "Using heuristic for next step (no StepCollection or playbook mismatch). "
            next_step_ip = self._get_next_step_heuristic(pb_name, ln_str, step_type)
            if next_step_ip:
                update_message += (
                    f"Heuristic suggests next step {next_step_ip.line_number}. "
                )
            else:
                update_message += (
                    "Heuristic suggests no next step (likely end of playbook). "
                )

        # Push the determined next step (if any)
        if next_step_ip:
            self.state.call_stack.push(
                CallStackFrame(
                    instruction_pointer=next_step_ip, llm_chat_session_id=None
                )
            )
            update_message += f"Pushed frame for {next_step_ip}."
        else:
            update_message += "Did not push a new frame."
            if self.state.call_stack.is_empty():
                self.state.request_exit(
                    "Call stack empty after reaching end of playbook", False
                )
                update_message += " Call stack is now empty."

        self.trace(update_message)

    def _get_next_step_heuristic(
        self, playbook: str, line_number: str, step_type: str
    ) -> InstructionPointer | None:
        """Heuristic to determine the next step when StepCollection is unavailable.

        - For YLD, attempts to increment the line number.
        - For others, assumes execution stays on the same line (to be re-evaluated by LLM).
        - Includes basic checks to avoid infinite loops on potentially last lines.

        Args:
            playbook: The playbook name.
            line_number: The line number string (e.g., "01", "01.01").
            step_type: The step type (e.g., "YLD", "CMD").

        Returns:
            An InstructionPointer for the guessed next step, or None if it seems like the end.
        """
        self.trace(
            f"Applying heuristic for step after {playbook}:{line_number}:{step_type}"
        )

        # For YLD instructions, we *must* advance to avoid infinite loops.
        if step_type == "YLD":
            try:
                if "." in line_number:  # Nested line "01.01"
                    parent, sub = line_number.split(".", 1)
                    # Basic check: If sub-line is high, assume it might be the last.
                    if int(sub) >= 90:  # Arbitrary threshold
                        self.trace(
                            f"Assuming YLD at nested line {line_number} is the last, returning None."
                        )
                        return None
                    next_line = f"{parent}.{int(sub) + 1:02d}"
                else:  # Simple line "01"
                    # Basic check: If line number is high, assume it might be the last.
                    if int(line_number) >= 90:  # Arbitrary threshold
                        self.trace(
                            f"Assuming YLD at line {line_number} is the last, returning None."
                        )
                        return None
                    next_line = f"{int(line_number) + 1:02d}"

                self.trace(
                    f"Heuristic for YLD: Advancing from {line_number} to {next_line}"
                )
                return InstructionPointer(playbook=playbook, line_number=next_line)
            except ValueError:
                self.trace(
                    f"Error incrementing line number '{line_number}', staying on same line.",
                    level="WARNING",
                )
                # Fall through to default behavior if increment fails
            except Exception as e:
                self.trace(
                    f"Unexpected error calculating next line for YLD: {e}",
                    level="ERROR",
                )
                # Fall through

        # Default for non-YLD, non-RET: Push the *same* line number back.
        # The LLM is expected to decide the actual next step based on this context.
        self.trace(f"Heuristic for {step_type}: Staying on line {line_number}")
        return InstructionPointer(playbook=playbook, line_number=line_number)

    def __repr__(self):
        """Return a string representation of the interpreter execution state."""
        pb_klass = self.current_playbook.klass if self.current_playbook else "None"
        return f"{self.__class__.__name__}(current_playbook='{pb_klass}', state={self.state})"
