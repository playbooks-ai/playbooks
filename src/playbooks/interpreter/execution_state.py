"""Execution state management for the interpreter.

This module provides the ExecutionState class, which encapsulates the state
tracked during interpreter execution, including call stack, exit conditions,
and execution control flags.
"""

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from playbooks.call_stack import CallStack
from playbooks.interpreter.tool_execution import ToolExecution
from playbooks.types import ToolCall
from playbooks.variables import Variables

if TYPE_CHECKING:
    from playbooks.agent import Agent
    from playbooks.agent_thread import AgentThread
    from playbooks.interpreter.exit_conditions import ExitCondition
    from playbooks.interpreter.interpreter import Interpreter


@dataclass
class ExecutionState:
    """Centralized state management for interpreter execution.

    Encapsulates all state tracked during execution including call stack,
    exit conditions, control flags, and execution data.
    """

    # Core references
    interpreter: Optional["Interpreter"] = None
    agent: Optional["Agent"] = None
    agent_thread: Optional["AgentThread"] = None

    # Core execution state
    conversation_history: List[str] = field(default_factory=list)
    call_stack: CallStack = field(default_factory=CallStack)
    variables: Variables = field(default_factory=Variables)
    exit_conditions: List["ExitCondition"] = field(default_factory=list)

    # Execution control flags
    should_exit: bool = False
    exit_reason: Optional[str] = None
    wait_for_input: bool = False
    wait_for_external_event: bool = False
    missing_say_after_external_tool_call: bool = False
    user_input_required: bool = False

    # Step tracking
    last_executed_step: Optional[str] = None
    yielded_steps: Set[str] = field(default_factory=set)

    # Playbook and response tracking
    playbook_calls: List[str] = field(default_factory=list)
    response_chunks: List[str] = field(default_factory=list)

    # Tool execution tracking
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_executions: List[ToolExecution] = field(default_factory=list)

    # Prepared instruction tracking
    prepared_instruction: Optional[str] = None

    # Configuration
    max_iterations: int = os.getenv("PLAYBOOKS_MAX_ITERATIONS", 10)
    max_execution_time: int = os.getenv("PLAYBOOKS_MAX_EXECUTION_TIME", 60)  # seconds
    max_no_progress: int = os.getenv("PLAYBOOKS_MAX_NO_PROGRESS", 3)

    def reset(self) -> None:
        """Reset the execution state."""
        self.reset_exit_state()
        self.playbook_calls = []
        self.response_chunks = []
        self.tool_calls = []
        self.yielded_steps = set()
        self.prepared_instruction = None

    def progress_hash(self) -> int:
        """Compute a hash of the current execution state to detect lack of progress."""
        state = {
            "call_stack": str(self.call_stack.to_dict()),
            "variables": str(self.variables.to_dict()),
        }
        return hash(str(state))

    def register_exit_condition(self, exit_condition: "ExitCondition") -> None:
        """Register an exit condition to check during execution."""
        self.exit_conditions.append(exit_condition)

    def request_exit(self, reason: str, wait_for_input: bool = False) -> None:
        """Request an exit from the execution loop."""
        self.should_exit = True
        self.exit_reason = reason
        self.wait_for_input = wait_for_input
        self.wait_for_external_event = False

    def check_exit_conditions(
        self, context: Dict[str, Any]
    ) -> Optional["ExitCondition"]:
        """Check all registered exit conditions against the current context."""
        for exit_condition in self.exit_conditions:
            if exit_condition.check(context):
                self.should_exit = True
                self.exit_reason = exit_condition.reason
                self.wait_for_input = exit_condition.wait_for_external_event
                self.wait_for_external_event = exit_condition.wait_for_external_event
                return exit_condition
        return None

    def add_conversation_history(self, message: str) -> None:
        """Add a message to the conversation history."""
        self.conversation_history.append(message)

    def reset_exit_state(self) -> None:
        """Reset the exit-related flags."""
        self.should_exit = False
        self.exit_reason = None
        self.wait_for_input = False
        self.wait_for_external_event = False

    def clear_response_chunks(self) -> None:
        """Clear the response chunks."""
        self.response_chunks = []

    def clear_tool_calls(self) -> None:
        """Clear the tool calls and executions."""
        self.tool_calls = []
        self.tool_executions = []

    def add_playbook_call(self, playbook: str) -> None:
        """Add a playbook call made by the LLM."""
        self.playbook_calls.append(playbook)

    def clear_playbook_calls(self) -> None:
        """Clear the playbook calls."""
        self.playbook_calls = []

    def set_last_executed_step(self, step: str) -> None:
        """Set the last executed step."""
        self.last_executed_step = step

    def add_yielded_step(self, step: str) -> None:
        """Add a step to the set of yielded steps."""
        self.yielded_steps.add(step)

    def has_yielded_step(self, step: str) -> bool:
        """Check if a step has been yielded."""
        return step in self.yielded_steps

    def update_variables(self, variables: Dict) -> None:
        """Update the variables in the current scope."""
        self.variables.update(variables)

    def set_call_stack(self, updated_call_stack: List[str]) -> None:
        """Set the call stack based on LLM output."""
        self.call_stack = CallStack(updated_call_stack)

    def __repr__(self) -> str:
        """Return a string representation of the execution state."""
        return f"{self.call_stack.__repr__()}{self.variables.__repr__()}"
