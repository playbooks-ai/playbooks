"""Playbook execution module for the interpreter."""

from typing import TYPE_CHECKING, Dict, Generator

from ..trace_mixin import TraceMixin
from ..types import AgentResponseChunk

if TYPE_CHECKING:
    from ..playbook import Playbook
    from .interpreter import Interpreter


class PlaybookExecution(TraceMixin):
    """Represents the execution of a playbook."""

    def __init__(
        self,
        interpreter: "Interpreter",
        playbooks: Dict[str, "Playbook"],
        current_playbook: "Playbook",
        instruction: str,
        llm_config=None,
        stream=False,
    ):
        """Initialize a playbook execution.

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
        self.playbooks = playbooks
        self.current_playbook = current_playbook
        self.instruction = instruction
        self.llm_config = llm_config
        self.stream = stream
        self.wait_for_external_event: bool = False

    def execute(self) -> Generator[AgentResponseChunk, None, None]:
        """Execute the playbook.

        Returns:
            A generator of agent response chunks.
        """
        done = False
        while not done:
            self.trace(
                "Start iteration",
                metadata={
                    "playbook": self.current_playbook.klass,
                    "line_number": self.interpreter.call_stack.peek().instruction_pointer.line_number,
                    "instruction": self.instruction,
                },
            )
            # Import here to avoid circular imports
            from .interpreter_execution import InterpreterExecution

            interpreter_execution = InterpreterExecution(
                interpreter=self.interpreter,
                playbooks=self.playbooks,
                current_playbook=self.current_playbook,
                instruction=self.instruction,
                llm_config=self.llm_config,
                stream=self.stream,
            )
            self.trace(interpreter_execution)
            yield from interpreter_execution.execute()
            if interpreter_execution.wait_for_external_event:
                self.wait_for_external_event = True
                self.trace(
                    "Waiting for external event, exiting loop",
                )
                done = True

            if (
                self.interpreter.call_stack.peek().instruction_pointer.playbook
                != self.current_playbook.klass
            ):
                self.trace(
                    f"Switching to new playbook {self.interpreter.call_stack.peek().instruction_pointer.playbook}, exiting loop",
                )
                done = True

    def __repr__(self):
        """Return a string representation of the playbook execution."""
        return f"{self.current_playbook.klass}()"
