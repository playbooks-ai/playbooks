"""Main interpreter module for executing playbooks."""

import contextlib
import json
import os
import time
from typing import TYPE_CHECKING, Dict, Generator

from playbooks.call_stack import CallStack, CallStackFrame, InstructionPointer
from playbooks.trace_mixin import TraceMixin, TraceWalker
from playbooks.types import AgentResponseChunk
from playbooks.variables import Variables

if TYPE_CHECKING:
    from playbooks.config import LLMConfig
    from playbooks.playbook import Playbook


class Interpreter(TraceMixin):
    """Main interpreter class for executing playbooks."""

    def __init__(self):
        """Initialize the interpreter."""
        super().__init__()
        self.local_variables = Variables()
        self.global_like_variables = Variables()
        self.call_stack = CallStack()
        self.yield_requested_on_say: bool = False

        # Configuration
        self.max_iterations = 100
        self.max_execution_time = 120  # seconds

    def pop_from_call_stack(self):
        """Pop a frame from the call stack.

        Returns:
            The popped frame, or None if the call stack is empty.
        """
        if self.call_stack:
            return self.call_stack.pop()
        return None

    def manage_variables(self, new_vars):
        """Manage variables in the interpreter.

        Args:
            new_vars: The new variables to add.
        """
        # Update local variables
        for name, value in new_vars.items():
            self.local_variables.__setitem__(name, value, instruction_pointer=None)
        # Remove stale variables
        self.remove_stale_variables()

    def remove_stale_variables(self):
        """Remove stale variables from the interpreter."""
        # Logic to remove stale variables from local and global-like variables
        # This is a placeholder for the actual logic
        pass

    def integrate_trigger_matching(self):
        """Integrate trigger matching when call stack is empty."""
        # Logic to integrate trigger matching when call stack is empty
        # This is a placeholder for the actual logic
        pass

    def _compute_state_hash(self) -> int:
        """Compute a hash of the current execution state to detect lack of progress."""
        state = {
            "call_stack": str(self.call_stack.to_dict()),
            "variables": str(self.local_variables.to_dict()),
            "line_number": self.get_current_line_number(),
        }
        return hash(str(state))

    @contextlib.contextmanager
    def execution_loop(self):
        """Context manager for execution loops with safety limits and exit condition checks."""
        iteration_count = 0
        start_time = time.time()
        last_state_hash = None
        consecutive_no_progress = 0

        # Reset state at the beginning of the loop
        should_exit = False
        exit_reason = None

        def should_continue():
            nonlocal iteration_count
            nonlocal last_state_hash
            nonlocal consecutive_no_progress
            nonlocal should_exit
            nonlocal exit_reason

            # Increment iteration count
            iteration_count += 1

            # Check iteration limits
            if iteration_count >= self.max_iterations:
                should_exit = True
                exit_reason = f"Maximum iterations ({self.max_iterations}) reached"
                return False

            # Check time limits
            if (time.time() - start_time) >= self.max_execution_time:
                should_exit = True
                exit_reason = (
                    f"Maximum execution time ({self.max_execution_time}s) reached"
                )
                return False

            # Check if an exit condition was triggered
            if should_exit:
                return False

            # Check for lack of progress
            current_state_hash = self._compute_state_hash()
            if current_state_hash == last_state_hash:
                consecutive_no_progress += 1
                if consecutive_no_progress >= 3:
                    should_exit = True
                    exit_reason = "No progress detected after multiple iterations"
                    return False
            else:
                consecutive_no_progress = 0
                last_state_hash = current_state_hash

            # Check if call stack is empty
            if self.call_stack.is_empty():
                should_exit = True
                exit_reason = "Call stack is empty, execution complete"
                return False

            return True

        try:
            # This is what's returned by the with statement
            yield should_continue

        finally:
            # Cleanup code - runs when exiting the with block
            execution_time = time.time() - start_time
            self.trace(
                f"Loop completed after {iteration_count-1} iterations in {execution_time:.2f}s",
                metadata={"exit_reason": exit_reason},
            )

    def execute(
        self,
        playbooks: Dict[str, "Playbook"],
        instruction: str,
        llm_config: "LLMConfig" = None,
        stream: bool = False,
    ) -> Generator[AgentResponseChunk, None, None]:
        """Execute the interpreter.

        Args:
            playbooks: The available playbooks.
            instruction: The instruction to execute.
            llm_config: The LLM configuration.
            stream: Whether to stream the response.

        Returns:
            A generator of agent response chunks.
        """
        self.trace(
            "Start interpreter session",
            metadata={"instruction": instruction, "playbooks": list(playbooks.keys())},
        )

        # If call stack is empty, find initial playbook
        if self.call_stack.is_empty():
            # Find the first playbook whose trigger includes "BGN"
            current_playbook = [
                p
                for p in playbooks.values()
                if p.trigger and "BGN" in p.trigger["markdown"]
            ]
            current_playbook = next(iter(current_playbook), None)
            if not current_playbook:
                raise Exception("No initial playbook found")

            # Push the initial playbook to the call stack
            self.call_stack.push(
                CallStackFrame(
                    InstructionPointer(
                        playbook=current_playbook.klass,
                        line_number="01",
                    ),
                    llm_chat_session_id=None,
                )
            )

        with self.execution_loop() as should_continue:
            while should_continue():
                # Check if call stack is empty
                should_exit, _ = self.handle_empty_call_stack()
                if should_exit:
                    break

                # Get the current frame (we know it exists because handle_empty_call_stack didn't exit)
                current_playbook_name = self.get_current_playbook_name()
                current_playbook = playbooks[current_playbook_name]

                # Import here to avoid circular imports
                from playbooks.interpreter.playbook_execution import PlaybookExecution

                playbook_execution = PlaybookExecution(
                    interpreter=self,
                    playbooks=playbooks,
                    current_playbook=current_playbook,
                    instruction=instruction,
                    llm_config=llm_config,
                    stream=stream,
                )
                self.trace(playbook_execution)
                yield from playbook_execution.execute()
                yield from self.yield_trace()

                # Check if playbook execution is waiting for external event
                if playbook_execution.wait_for_external_event:
                    self.trace("Waiting for external event, exiting interpreter loop")
                    break

    def process_chunk(self, chunk):
        """Process a chunk from the LLM.

        Args:
            chunk: The chunk to process.
        """
        # Example processing logic for a chunk
        # print("Processing chunk:", chunk)
        # self.current_llm_session.process_chunk(chunk)
        # Here you can add logic to manage the call stack and variables based on the chunk
        # For now, just a placeholder
        pass

    def get_playbook_trigger_summary(self, playbook: "Playbook") -> str:
        """Get a summary of the playbook trigger.

        Args:
            playbook: The playbook to get the trigger summary for.

        Returns:
            A string summary of the playbook trigger.
        """
        strs = [f"- {playbook.signature}: {playbook.description}"]
        if playbook.trigger:
            strs.append(
                "\n".join(
                    [f"  - {t['markdown']}" for t in playbook.trigger["children"]]
                )
            )
        return "\n".join(strs)

    def get_prompt(
        self,
        playbooks: Dict[str, "Playbook"],
        current_playbook: "Playbook",
        instruction: str,
    ) -> str:
        """Get the prompt for the LLM.

        Args:
            playbooks: The available playbooks.
            current_playbook: The current playbook being executed.
            instruction: The instruction to execute.

        Returns:
            The prompt for the LLM.
        """
        playbooks_signatures = "\n".join(
            [
                self.get_playbook_trigger_summary(playbook)
                for playbook in playbooks.values()
            ]
        )
        current_playbook_markdown = playbooks[current_playbook.klass].markdown

        prompt = open(
            os.path.join(os.path.dirname(__file__), "../prompts/interpreter_run.txt"),
            "r",
        ).read()

        # initial_state =
        # {
        #     "thread_id": "main",
        #     "initial_call_stack": [CheckOrderStatusMain:01.01, AuthenticateUserPlaybook:03],
        #     "initial_variables": {
        #       "$isAuthenticated": false,
        #       "$email": abc7873@yahoo.com,
        #       "$pin": 8989
        #       "$authToken": null
        #     },
        #     "available_external_functions": [
        #         "Say($message) -> None: Say something to the user",
        #         "Handoff() -> None: Connects the user to a human",
        #     ]
        # }
        initial_state = json.dumps(
            {
                "thread_id": "main",
                "initial_call_stack": self.call_stack.to_dict(),
                "initial_variables": self.local_variables.to_dict(),
            },
            indent=2,
        )

        # print(initial_state)

        prompt = prompt.replace("{{PLAYBOOKS_SIGNATURES}}", playbooks_signatures)
        prompt = prompt.replace(
            "{{CURRENT_PLAYBOOK_MARKDOWN}}", current_playbook_markdown
        )
        prompt = prompt.replace("{{SESSION_CONTEXT}}", self.session_context())
        prompt = prompt.replace("{{INITIAL_STATE}}", initial_state)
        prompt = prompt.replace("{{INSTRUCTION}}", instruction)

        return prompt

    def session_context(self):
        """Get the session context.

        Returns:
            A string representation of the session context.
        """
        items = []
        TraceWalker.walk(
            self,
            lambda item: (
                items.append(item)
                if item.item.__class__.__name__
                in (
                    "StepExecution",
                    "MessageReceived",
                    "ToolExecutionResult",
                )
                else None
            ),
        )

        log = []
        for item in items:
            lines = item.item.__repr__().split("\n")
            log.append("- " + lines[0])
            if len(lines) > 1:
                for line in lines[1:]:
                    log.append("  " + line)
        return "\n".join(log)

    def handle_empty_call_stack(self, trace_context=None):
        """Handle the case where the call stack is empty.

        Args:
            trace_context: Optional context to include in the trace metadata.

        Returns:
            A tuple of (should_exit, exit_reason) indicating that execution should stop.
        """
        # Check if call stack is empty
        if self.call_stack.is_empty():
            # Prepare trace metadata
            metadata = {"reason": "Call stack is empty"}
            if trace_context:
                metadata.update(trace_context)

            # Return exit flags
            return True, "Call stack is empty"

        # Call stack is not empty
        return False, None

    def get_current_line_number(self, default="END"):
        """Get the current line number from the call stack.

        Args:
            default: The default value to return if the call stack is empty.

        Returns:
            The current line number, or the default value if the call stack is empty.
        """
        current_frame = self.call_stack.peek()
        return (
            default
            if current_frame is None
            else current_frame.instruction_pointer.line_number
        )

    def get_current_playbook_name(self, default=None):
        """Get the current playbook name from the call stack.

        Args:
            default: The default value to return if the call stack is empty.

        Returns:
            The current playbook name, or the default value if the call stack is empty.
        """
        current_frame = self.call_stack.peek()
        return (
            default
            if current_frame is None
            else current_frame.instruction_pointer.playbook
        )
