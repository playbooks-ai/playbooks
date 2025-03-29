"""Instruction pointer module for the interpreter.

This module provides the InstructionPointer class, which represents a pointer to
a specific line in a playbook. It is used to track the current execution position
in a playbook and manage the call stack.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class InstructionPointer:
    """Represents a pointer to a specific line in a playbook.

    This class is used to track the current execution position in a playbook.
    It contains information about the playbook name and the line number being
    executed.

    Attributes:
        playbook (str): The name of the playbook.
        line_number (str): The line number in the playbook.
        llm_chat_session_id (Optional[str]): The ID of the LLM chat session.
    """

    playbook: str
    line_number: str
    llm_chat_session_id: Optional[str] = None

    def __str__(self) -> str:
        """Return a string representation of the instruction pointer.

        Returns:
            A string in the format "playbook:line_number".
        """
        return f"{self.playbook}:{self.line_number}"

    def __eq__(self, other: object) -> bool:
        """Check if this instruction pointer is equal to another.

        Args:
            other: The other object to compare with.

        Returns:
            True if the instruction pointers are equal, False otherwise.
        """
        if not isinstance(other, InstructionPointer):
            return NotImplemented
        return (
            self.playbook == other.playbook
            and self.line_number == other.line_number
            and self.llm_chat_session_id == other.llm_chat_session_id
        )

    def __hash__(self) -> int:
        """Return a hash of the instruction pointer.

        Returns:
            A hash value for the instruction pointer.
        """
        return hash((self.playbook, self.line_number, self.llm_chat_session_id))
