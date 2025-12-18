"""Enhanced SessionLogItem types for comprehensive execution tracking."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from playbooks.llm.messages.timestamp import get_timestamp
from playbooks.state.session_log import SessionLogItem


@dataclass
class SessionLogItemBase(SessionLogItem):
    """Base class for all enhanced session log items with metadata."""

    timestamp: int
    agent_id: str
    agent_klass: str

    def __post_init__(self):
        """Set timestamp if not provided."""
        if not hasattr(self, "_timestamp_set"):
            # If timestamp is 0 or not set, get current timestamp
            if self.timestamp == 0:
                object.__setattr__(self, "timestamp", get_timestamp())
            object.__setattr__(self, "_timestamp_set", True)

    @property
    def item_type(self) -> str:
        """Return the type identifier for this log item.

        Derives type from class name by removing "SessionLogItem" prefix
        and converting to lowercase.

        Returns:
            Type identifier string (e.g., "playbookstart", "llmrequest")
        """
        return self.__class__.__name__.replace("SessionLogItem", "").lower()

    def to_metadata(self) -> Dict[str, Any]:
        """Convert to metadata dict for streaming.

        Returns:
            Dictionary containing base metadata (type, timestamp, agent info)
        """
        return {
            "type": self.item_type,
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "agent_klass": self.agent_klass,
        }


@dataclass
class SessionLogItemPlaybookStart(SessionLogItemBase):
    """Marks the start of a playbook execution."""

    playbook_name: str
    playbook_id: Optional[str] = None
    parent_playbook: Optional[str] = None

    def to_log_full(self) -> str:
        """Generate full log message for this item.

        Returns:
            Formatted log message string
        """
        return f"▶ Starting playbook: {self.playbook_name}"

    def to_metadata(self) -> Dict[str, Any]:
        meta = super().to_metadata()
        meta.update(
            {
                "playbook_name": self.playbook_name,
                "playbook_id": self.playbook_id,
                "parent_playbook": self.parent_playbook,
            }
        )
        return meta


@dataclass
class SessionLogItemPlaybookEnd(SessionLogItemBase):
    """Marks the end of a playbook execution."""

    playbook_name: str
    playbook_id: Optional[str] = None
    return_value: Any = None
    execution_time_ms: Optional[int] = None
    success: bool = True
    error: Optional[str] = None

    def to_log_full(self) -> str:
        status = "✓" if self.success else "✗"
        msg = f"{status} Finished playbook: {self.playbook_name}"
        if self.execution_time_ms:
            msg += f" ({self.execution_time_ms}ms)"
        if self.error:
            msg += f" - Error: {self.error}"
        elif self.return_value is not None:
            msg += f" → {self.return_value}"
        return msg

    def to_metadata(self) -> Dict[str, Any]:
        meta = super().to_metadata()
        meta.update(
            {
                "playbook_name": self.playbook_name,
                "playbook_id": self.playbook_id,
                "return_value": str(self.return_value) if self.return_value else None,
                "execution_time_ms": self.execution_time_ms,
                "success": self.success,
                "error": self.error,
            }
        )
        return meta


@dataclass
class SessionLogItemLLMRequest(SessionLogItemBase):
    """Tracks LLM API requests."""

    model: str
    messages: List[Dict[str, str]]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    def to_log_full(self) -> str:
        msg_count = len(self.messages)
        return f"🤖 LLM Request to {self.model} ({msg_count} messages)"

    def to_metadata(self) -> Dict[str, Any]:
        meta = super().to_metadata()
        meta.update(
            {
                "model": self.model,
                "messages": self.messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
        )
        return meta


@dataclass
class SessionLogItemLLMResponse(SessionLogItemBase):
    """Tracks LLM API responses."""

    model: str
    content: str
    usage: Optional[Dict[str, int]] = None
    response_time_ms: Optional[int] = None

    def to_log_full(self) -> str:
        msg = f"💬 LLM Response from {self.model}"
        if self.response_time_ms:
            msg += f" ({self.response_time_ms}ms)"
        if self.usage:
            msg += f" - Tokens: {self.usage.get('total_tokens', 'N/A')}"
        msg += (
            f"\n{self.content[:200]}..."
            if len(self.content) > 200
            else f"\n{self.content}"
        )
        return msg

    def to_metadata(self) -> Dict[str, Any]:
        meta = super().to_metadata()
        meta.update(
            {
                "model": self.model,
                "content": self.content,
                "usage": self.usage,
                "response_time_ms": self.response_time_ms,
            }
        )
        return meta


@dataclass
class SessionLogItemStepExecution(SessionLogItemBase):
    """Tracks individual step execution within a playbook."""

    step_name: str
    step_type: str  # "trigger", "step", "condition", etc.
    step_content: str
    playbook_name: str

    def to_log_full(self) -> str:
        return (
            f"→ {self.step_type.capitalize()}: {self.step_name} - {self.step_content}"
        )

    def to_metadata(self) -> Dict[str, Any]:
        meta = super().to_metadata()
        meta.update(
            {
                "step_name": self.step_name,
                "step_type": self.step_type,
                "step_content": self.step_content,
                "playbook_name": self.playbook_name,
            }
        )
        return meta


@dataclass
class SessionLogItemVariableUpdate(SessionLogItemBase):
    """Tracks variable updates during execution."""

    variable_name: str
    old_value: Any
    new_value: Any
    scope: str  # "local", "global", etc.

    def to_log_full(self) -> str:
        return f"📝 {self.variable_name} = {self.new_value} (was: {self.old_value})"

    def to_metadata(self) -> Dict[str, Any]:
        meta = super().to_metadata()
        meta.update(
            {
                "variable_name": self.variable_name,
                "old_value": str(self.old_value),
                "new_value": str(self.new_value),
                "scope": self.scope,
            }
        )
        return meta


@dataclass
class SessionLogItemAgentMessage(SessionLogItemBase):
    """Tracks agent-to-agent messages."""

    sender_id: str
    sender_klass: str
    recipient_id: str
    recipient_klass: str
    message: str
    message_type: str

    def to_log_full(self) -> str:
        return f"📨 {self.sender_klass}({self.sender_id}) → {self.recipient_klass}({self.recipient_id}): {self.message}"

    def to_metadata(self) -> Dict[str, Any]:
        meta = super().to_metadata()
        meta.update(
            {
                "sender_id": self.sender_id,
                "sender_klass": self.sender_klass,
                "recipient_id": self.recipient_id,
                "recipient_klass": self.recipient_klass,
                "message": self.message,
                "message_type": self.message_type,
            }
        )
        return meta


@dataclass
class SessionLogItemError(SessionLogItemBase):
    """Tracks errors during execution."""

    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

    def to_log_full(self) -> str:
        msg = f"❌ {self.error_type}: {self.error_message}"
        if self.stack_trace:
            msg += f"\n{self.stack_trace}"
        return msg

    def to_metadata(self) -> Dict[str, Any]:
        meta = super().to_metadata()
        meta.update(
            {
                "error_type": self.error_type,
                "error_message": self.error_message,
                "stack_trace": self.stack_trace,
                "context": self.context,
            }
        )
        return meta


@dataclass
class SessionLogItemDebug(SessionLogItemBase):
    """Debug information during execution."""

    message: str
    data: Optional[Dict[str, Any]] = None

    def to_log_full(self) -> str:
        msg = f"🐛 {self.message}"
        if self.data:
            msg += f" - {self.data}"
        return msg

    def to_metadata(self) -> Dict[str, Any]:
        meta = super().to_metadata()
        meta.update(
            {
                "message": self.message,
                "data": self.data,
            }
        )
        return meta
