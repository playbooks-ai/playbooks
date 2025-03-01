"""Main interpreter module for executing playbooks."""

import json
import os
from typing import TYPE_CHECKING, Dict, Generator

from ..call_stack import CallStack, CallStackFrame, InstructionPointer
from ..trace_mixin import TraceMixin, TraceWalker
from ..types import AgentResponseChunk
from ..variables import Variables

if TYPE_CHECKING:
    from ..config import LLMConfig
    from ..playbook import Playbook


class Interpreter(TraceMixin):
    """Main interpreter class for executing playbooks."""

    def __init__(self):
        """Initialize the interpreter."""
        super().__init__()
        self.local_variables = Variables()
        self.global_like_variables = Variables()
        self.call_stack = CallStack()
        self.yield_requested_on_say: bool = False

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
        print(self.to_trace())
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

        done = False
        while not done:
            current_playbook = playbooks[
                self.call_stack.peek().instruction_pointer.playbook
            ]

            # Import here to avoid circular imports
            from .playbook_execution import PlaybookExecution

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
            if playbook_execution.wait_for_external_event:
                done = True

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
