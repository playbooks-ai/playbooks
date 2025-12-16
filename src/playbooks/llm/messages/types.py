"""Clean semantic LLM message types with minimal, maintainable design."""

import os
from typing import Any, Dict, Optional

from playbooks.core.enums import LLMMessageRole, LLMMessageType
from playbooks.llm.messages.base import LLMMessage
from playbooks.state.variables import Artifact

# Core semantic message types - minimal set covering all use cases


class SystemPromptLLMMessage(LLMMessage):
    """System prompts and instructions."""

    def __init__(self) -> None:
        # Load system prompt from file
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "prompts",
            "interpreter_run.txt",
        )

        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                system_prompt = f.read().strip()
        except FileNotFoundError:
            raise FileNotFoundError(f"System prompt file not found: {prompt_path}")

        super().__init__(
            content=system_prompt,
            role=LLMMessageRole.SYSTEM,
            type=LLMMessageType.SYSTEM_PROMPT,
        )


class UserInputLLMMessage(LLMMessage):
    """User inputs and instructions with component-based storage.

    Components:
    - about_you: Optional section with agent context (starts with "Remember:")
    - instruction: The main instruction to execute
    - python_code_context: Optional Python context section with execution state
    - final_instructions: Optional closing instructions (starts with "Carefully analyze...")
    """

    def __init__(
        self,
        about_you: str = "",
        instruction: str = "",
        python_code_context: str = "",
        final_instructions: str = "",
    ) -> None:
        """Initialize UserInputLLMMessage with components.

        Args:
            about_you: Agent context section
            instruction: Main instruction
            python_code_context: Python execution context
            final_instructions: Closing instructions
        """
        # Store components
        self.about_you = about_you
        self.instruction = instruction
        self.python_code_context = python_code_context
        self.final_instructions = final_instructions

        # Build content from components
        parts = []
        if self.about_you:
            parts.append(self.about_you)
        if self.python_code_context:
            parts.append(self.python_code_context)
        if self.instruction:
            parts.append(self.instruction)
        if self.final_instructions:
            parts.append(self.final_instructions)

        super().__init__(
            content="\n\n".join(parts),
            role=LLMMessageRole.USER,
            type=LLMMessageType.USER_INPUT,
        )

    def to_compact_message(self) -> Optional[Dict[str, Any]]:
        """Return message with only the instruction component."""
        return {"role": self.role.value, "content": self.instruction}

    def __eq__(self, other: object) -> bool:
        """Check equality including component attributes."""
        if not isinstance(other, self.__class__):
            return False
        return (
            super().__eq__(other)
            and self.about_you == other.about_you
            and self.instruction == other.instruction
            and self.python_code_context == other.python_code_context
            and self.final_instructions == other.final_instructions
        )

    def __hash__(self) -> int:
        """Hash including component attributes."""
        return hash(
            (
                self.__class__.__name__,
                self.content,
                self.role,
                self.type,
                self.about_you,
                self.instruction,
                self.python_code_context,
                self.final_instructions,
            )
        )


class AssistantResponseLLMMessage(LLMMessage):
    """LLM responses."""

    def __init__(self, content: str) -> None:
        super().__init__(
            content=content,
            role=LLMMessageRole.ASSISTANT,
            type=LLMMessageType.ASSISTANT_RESPONSE,
        )

    def to_compact_message(self) -> Dict[str, Any]:
        """Use first two lines (execution_id and recap) for compaction."""
        lines = self.content.strip("```python").strip("```").strip().split("\n")
        lines = lines[:2]
        return {"role": self.role.value, "content": "\n".join(lines)}

    def set_content(self, content: str) -> None:
        """
        Set the content of the message.

        This violoates the immutability of the message. But, we need to do this
        because the content is not available until the LLM call is complete.

        Args:
            content: The content to set
        """
        self._content = content


class PlaybookImplementationLLMMessage(LLMMessage):
    """Playbook markdown implementation."""

    def __init__(self, content: str, playbook_name: str) -> None:
        self.playbook_name = self._validate_string_param(playbook_name, "playbook_name")

        super().__init__(
            content=content,
            role=LLMMessageRole.USER,
            type=LLMMessageType.PLAYBOOK_IMPLEMENTATION,
        )

    def __eq__(self, other: object) -> bool:
        """Check equality including custom attributes."""
        if not isinstance(other, self.__class__):
            return False
        return super().__eq__(other) and self.playbook_name == other.playbook_name

    def __hash__(self) -> int:
        """Hash including custom attributes."""
        return hash(
            (
                self.__class__.__name__,
                self.content,
                self.role,
                self.type,
                self.playbook_name,
            )
        )


class ExecutionResultLLMMessage(LLMMessage):
    """Playbook execution results."""

    def __init__(self, content: str, playbook_name: str, success: bool = True) -> None:
        self.playbook_name = self._validate_string_param(playbook_name, "playbook_name")
        if not isinstance(success, bool):
            raise TypeError(f"success must be a boolean, got {type(success).__name__}")
        self.success = success

        super().__init__(
            content=content,
            role=LLMMessageRole.USER,
            type=LLMMessageType.EXECUTION_RESULT,
        )

    def __eq__(self, other: object) -> bool:
        """Check equality including custom attributes."""
        if not isinstance(other, self.__class__):
            return False
        return (
            super().__eq__(other)
            and self.playbook_name == other.playbook_name
            and self.success == other.success
        )

    def __hash__(self) -> int:
        """Hash including custom attributes."""
        return hash(
            (
                self.__class__.__name__,
                self.content,
                self.role,
                self.type,
                self.playbook_name,
                self.success,
            )
        )


class AgentCommunicationLLMMessage(LLMMessage):
    """Inter-agent communications."""

    def __init__(self, content: str, sender_agent: str, target_agent: str) -> None:
        self.sender_agent = self._validate_string_param(sender_agent, "sender_agent")
        self.target_agent = self._validate_string_param(target_agent, "target_agent")

        # Note: sender_agent can be the same as target_agent in meeting contexts
        # or when an agent is processing its own messages

        super().__init__(
            content=content,
            role=LLMMessageRole.USER,
            type=LLMMessageType.AGENT_COMMUNICATION,
        )

    def __eq__(self, other: object) -> bool:
        """Check equality including custom attributes."""
        if not isinstance(other, self.__class__):
            return False
        return (
            super().__eq__(other)
            and self.sender_agent == other.sender_agent
            and self.target_agent == other.target_agent
        )

    def __hash__(self) -> int:
        """Hash including custom attributes."""
        return hash(
            (
                self.__class__.__name__,
                self.content,
                self.role,
                self.type,
                self.sender_agent,
                self.target_agent,
            )
        )


class MeetingLLMMessage(LLMMessage):
    """Meeting-related communications."""

    def __init__(self, content: str, meeting_id: str) -> None:
        self.meeting_id = self._validate_string_param(meeting_id, "meeting_id")

        super().__init__(
            content=content,
            role=LLMMessageRole.USER,
            type=LLMMessageType.MEETING_MESSAGE,
        )

    def __eq__(self, other: object) -> bool:
        """Check equality including custom attributes."""
        if not isinstance(other, self.__class__):
            return False
        return super().__eq__(other) and self.meeting_id == other.meeting_id

    def __hash__(self) -> int:
        """Hash including custom attributes."""
        return hash(
            (
                self.__class__.__name__,
                self.content,
                self.role,
                self.type,
                self.meeting_id,
            )
        )


class TriggerInstructionsLLMMessage(LLMMessage):
    """Playbook trigger instructions."""

    def __init__(self, content: str) -> None:
        super().__init__(
            content=content,
            role=LLMMessageRole.USER,
            type=LLMMessageType.TRIGGER_INSTRUCTIONS,
        )


class AgentInfoLLMMessage(LLMMessage):
    """Current agent information."""

    def __init__(self, content: str) -> None:
        super().__init__(
            content=content,
            role=LLMMessageRole.USER,
            type=LLMMessageType.AGENT_INFO,
        )


class OtherAgentInfoLLMMessage(LLMMessage):
    """Other available agents information."""

    def __init__(self, content: str) -> None:
        super().__init__(
            content=content,
            role=LLMMessageRole.USER,
            type=LLMMessageType.OTHER_AGENT_INFO,
        )


class FileLoadLLMMessage(LLMMessage):
    """File content loading."""

    def __init__(self, content: str, file_path: str) -> None:
        self.file_path = self._validate_string_param(file_path, "file_path")
        # Note: Content size validation is now handled by base class

        super().__init__(
            content=content,
            role=LLMMessageRole.USER,
            type=LLMMessageType.FILE_LOAD,
        )

    def __eq__(self, other: object) -> bool:
        """Check equality including custom attributes."""
        if not isinstance(other, self.__class__):
            return False
        return super().__eq__(other) and self.file_path == other.file_path

    def __hash__(self) -> int:
        """Hash including custom attributes."""
        return hash(
            (
                self.__class__.__name__,
                self.content,
                self.role,
                self.type,
                self.file_path,
            )
        )


class SessionLogLLMMessage(LLMMessage):
    """Session logging and status updates."""

    def __init__(self, content: str, log_level: str = "INFO") -> None:
        # Validate log level
        valid_levels = {"DEBUG", "INFO", "WARN", "ERROR", "FATAL"}
        if not isinstance(log_level, str):
            raise TypeError(
                f"log_level must be a string, got {type(log_level).__name__}"
            )
        if log_level not in valid_levels:
            raise ValueError(
                f"log_level must be one of {valid_levels}, got {log_level!r}"
            )
        self.log_level = log_level

        super().__init__(
            content=content,
            role=LLMMessageRole.SYSTEM,  # Fixed: logs are system-level information
            type=LLMMessageType.SESSION_LOG,
        )

    def __eq__(self, other: object) -> bool:
        """Check equality including custom attributes."""
        if not isinstance(other, self.__class__):
            return False
        return super().__eq__(other) and self.log_level == other.log_level

    def __hash__(self) -> int:
        """Hash including custom attributes."""
        return hash(
            (
                self.__class__.__name__,
                self.content,
                self.role,
                self.type,
                self.log_level,
            )
        )


class ArtifactLLMMessage(LLMMessage):
    """Artifacts."""

    def __init__(self, artifact: Artifact) -> None:
        self.artifact = artifact

        super().__init__(
            content=f"**Artifact {('$' + artifact.name) if not artifact.name.startswith('$') else artifact.name}**\n\n*Summary:*\n{artifact.summary}\n\n*Contents:*\n{artifact.value}\n\n",
            role=LLMMessageRole.USER,
            type=LLMMessageType.ARTIFACT,
        )
