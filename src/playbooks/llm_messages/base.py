"""Base LLMMessage class for handling LLM messages."""

from typing import Any, Dict, Optional

from ..enums import LLMMessageRole, LLMMessageType


class LLMMessage:
    """Base class for all LLM messages.

    This class provides a structured way to handle messages sent to and from LLMs,
    with support for different roles, types, and caching strategies.

    Attributes:
        content: The text content of the message
        role: The role of the message sender (system, user, assistant)
        type: The type of message
        cached: Whether this message should be cached by the LLM provider
    """

    # Class-level constants for validation
    MAX_CONTENT_SIZE = 100_000  # 100K char limit
    MIN_CONTENT_SIZE = 0  # Allow empty content for some use cases

    def __init__(
        self,
        content: str,
        role: LLMMessageRole,
        type: LLMMessageType = LLMMessageType.USER_INPUT,
        cached: bool = False,
    ) -> None:
        """Initialize an LLMMessage.

        Args:
            content: The text content of the message
            role: The role of the message sender
            type: The type of message (defaults to USER_INPUT)
            cached: Whether this message should be cached

        Raises:
            TypeError: If content is not a string
            ValueError: If content or other parameters are invalid
        """
        # Validate and normalize content
        self._content = self._validate_content(content)

        # Validate role and type
        self._role = self._validate_role(role)
        self._type = self._validate_type(type)

        # Validate cached flag
        self._cached = self._validate_cached(cached)

    @staticmethod
    def _validate_content(content: str) -> str:
        """Validate and normalize content.

        Args:
            content: The content to validate

        Returns:
            The validated content string

        Raises:
            TypeError: If content is not a string
            ValueError: If content is invalid
        """
        if content is None:
            raise TypeError("content cannot be None")

        if not isinstance(content, str):
            raise TypeError(f"content must be a string, got {type(content).__name__}")

        # Check size limits
        if len(content) > LLMMessage.MAX_CONTENT_SIZE:
            raise ValueError(
                f"content too large: {len(content)} bytes > {LLMMessage.MAX_CONTENT_SIZE} bytes"
            )

        # Content can be empty for some valid use cases, so we allow it
        # But we normalize whitespace-only strings to empty strings
        normalized = content.strip()
        if not normalized and content:  # Had content but only whitespace
            # For most cases, whitespace-only content is probably an error
            # but we'll allow it and normalize to empty string
            return ""

        return content  # Return original to preserve intentional whitespace

    @staticmethod
    def _validate_role(role: LLMMessageRole) -> LLMMessageRole:
        """Validate role parameter.

        Args:
            role: The role to validate

        Returns:
            The validated role

        Raises:
            TypeError: If role is not an LLMMessageRole
        """
        if not isinstance(role, LLMMessageRole):
            raise TypeError(
                f"role must be an LLMMessageRole, got {type(role).__name__}"
            )
        return role

    @staticmethod
    def _validate_type(msg_type: LLMMessageType) -> LLMMessageType:
        """Validate type parameter.

        Args:
            msg_type: The message type to validate

        Returns:
            The validated message type

        Raises:
            TypeError: If msg_type is not an LLMMessageType
        """
        if not isinstance(msg_type, LLMMessageType):
            raise TypeError(
                f"type must be an LLMMessageType, got {type(msg_type).__name__}"
            )
        return msg_type

    @staticmethod
    def _validate_cached(cached: bool) -> bool:
        """Validate cached parameter.

        Args:
            cached: The cached flag to validate

        Returns:
            The validated cached flag

        Raises:
            TypeError: If cached is not a boolean
        """
        if not isinstance(cached, bool):
            raise TypeError(f"cached must be a boolean, got {type(cached).__name__}")
        return cached

    @staticmethod
    def _validate_string_param(
        value: Any, param_name: str, allow_empty: bool = False
    ) -> str:
        """Validate a string parameter with common rules.

        Args:
            value: The value to validate
            param_name: Name of the parameter for error messages
            allow_empty: Whether to allow empty strings

        Returns:
            The validated string

        Raises:
            TypeError: If value is not a string
            ValueError: If value is invalid
        """
        if value is None:
            raise TypeError(f"{param_name} cannot be None")

        if not isinstance(value, str):
            raise TypeError(
                f"{param_name} must be a string, got {type(value).__name__}"
            )

        # Check for whitespace-only strings
        if not value.strip():
            if allow_empty and not value:
                return value  # Allow truly empty strings if specified
            raise ValueError(f"{param_name} cannot be empty or whitespace-only")

        return value

    # Properties for immutability
    @property
    def content(self) -> str:
        """Get the message content."""
        return self._content

    @property
    def role(self) -> LLMMessageRole:
        """Get the message role."""
        return self._role

    @property
    def type(self) -> LLMMessageType:
        """Get the message type."""
        return self._type

    @property
    def cached(self) -> bool:
        """Get the cached flag."""
        return self._cached

    def to_full_message(self) -> Dict[str, Any]:
        """Convert to full dictionary representation for LLM APIs.

        Returns:
            A dictionary with role, type, content, and optionally cache_control fields
        """
        message = {
            "role": self.role.value,
            "type": self.type.value,
            "content": self.content,
        }
        if self.cached:
            message["cache_control"] = {"type": "ephemeral"}
        return message

    def to_compact_message(self) -> Optional[Dict[str, Any]]:
        """Convert to compact representation for token optimization.

        This method can be extended in the future to provide
        progressive compaction strategies for reducing token usage.

        Returns:
            A dictionary representation or None to remove completely
        """
        # Default implementation returns full message
        # Can be overridden in subclasses for specific compaction strategies
        return self.to_full_message()

    def __repr__(self) -> str:
        """String representation of the message."""
        cached_str = ", cached=True" if self.cached else ""
        return f"{self.__class__.__name__}(role={self.role}, type={self.type}, content_length={len(self.content)}{cached_str})"

    def __eq__(self, other: object) -> bool:
        """Check equality with another message.

        Subclasses should override this to include their custom attributes.
        """
        if not isinstance(other, self.__class__):
            return False
        return (
            self.content == other.content
            and self.role == other.role
            and self.type == other.type
            and self.cached == other.cached
        )

    def __hash__(self) -> int:
        """Make messages hashable for use in sets and as dict keys.

        Subclasses should override this to include their custom attributes.
        """
        return hash(
            (self.__class__.__name__, self.content, self.role, self.type, self.cached)
        )
