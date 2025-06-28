"""
Simplified message delivery system for agent communication.

This module provides a unified inbox approach where:
- Each agent has a single inbox for all messages
- Agents have explicit waiting modes 
- A centralized processor delivers messages in batches when conditions are met
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from playbooks.agents.base_agent import BaseAgent


class WaitingMode(Enum):
    """Defines what an agent is currently waiting for."""

    NOT_WAITING = "not_waiting"
    WAITING_AGENT = "waiting_agent"  # Waiting for any agent (including human)
    WAITING_MEETING = "waiting_meeting"


@dataclass
class AgentMessage:
    """Represents a message in the system."""

    sender_id: str
    content: str
    message_type: str = "direct"  # direct, meeting_invite, meeting_message, etc.
    meeting_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AgentWaitingState:
    """Tracks what an agent is waiting for."""

    mode: WaitingMode = WaitingMode.NOT_WAITING
    target_agent_id: Optional[str] = None  # For WAITING_AGENT
    target_meeting_id: Optional[str] = None  # For WAITING_MEETING
    first_message_time: Optional[datetime] = None  # When first message arrived
    meeting_timeout_seconds: float = 5.0  # How long to wait for more meeting messages


class SimplifiedInbox:
    """Single inbox per agent with waiting state management."""

    def __init__(self):
        self.messages: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self.waiting_state = AgentWaitingState()

    def add_message(self, message: AgentMessage):
        """Add a message to the inbox."""
        # Track when first message arrived for meeting timeout logic
        if (
            self.waiting_state.mode == WaitingMode.WAITING_MEETING
            and self.waiting_state.first_message_time is None
        ):
            self.waiting_state.first_message_time = message.timestamp

        self.messages.put_nowait(message)

    def set_waiting_mode(
        self,
        mode: WaitingMode,
        target_agent_id: str = None,
        target_meeting_id: str = None,
        timeout_seconds: float = 5.0,
    ):
        """Set what this agent is waiting for."""
        self.waiting_state.mode = mode
        self.waiting_state.target_agent_id = target_agent_id
        self.waiting_state.target_meeting_id = target_meeting_id
        self.waiting_state.meeting_timeout_seconds = timeout_seconds
        self.waiting_state.first_message_time = None

    def check_delivery_condition(self) -> bool:
        """Check if delivery conditions are met for this inbox."""
        if self.messages.empty():
            return False

        # Peek at messages without removing them
        messages = self._peek_all_messages()

        # Always deliver meeting invitations regardless of waiting state
        has_meeting_invite = any(
            msg.message_type == "meeting_invite" for msg in messages
        )
        if has_meeting_invite:
            return True

        if self.waiting_state.mode == WaitingMode.NOT_WAITING:
            return False

        if self.waiting_state.mode == WaitingMode.WAITING_AGENT:
            # Deliver if there's a direct message from the target agent (including human)
            return any(
                msg.sender_id == self.waiting_state.target_agent_id
                and msg.message_type == "direct"
                for msg in messages
            )

        elif self.waiting_state.mode == WaitingMode.WAITING_MEETING:
            # Deliver if:
            # 1. There's a meeting message directed at this agent, OR
            # 2. Enough time has passed since first message
            has_meeting_message = any(
                msg.meeting_id == self.waiting_state.target_meeting_id
                and msg.message_type in ["meeting_message", "direct"]
                for msg in messages
            )

            if has_meeting_message:
                return True

            # Check timeout
            if self.waiting_state.first_message_time:
                elapsed = (
                    datetime.now() - self.waiting_state.first_message_time
                ).total_seconds()
                return elapsed >= self.waiting_state.meeting_timeout_seconds

        return False

    def _peek_all_messages(self) -> List[AgentMessage]:
        """Get all messages without removing them from queue."""
        messages = []
        temp_messages = []

        # Extract all messages
        while not self.messages.empty():
            try:
                msg = self.messages.get_nowait()
                messages.append(msg)
                temp_messages.append(msg)
            except asyncio.QueueEmpty:
                break

        # Put them back
        for msg in temp_messages:
            self.messages.put_nowait(msg)

        return messages

    def get_all_messages(self) -> List[AgentMessage]:
        """Get and remove all messages from the inbox."""
        messages = []
        while not self.messages.empty():
            try:
                messages.append(self.messages.get_nowait())
            except asyncio.QueueEmpty:
                break

        # Reset waiting state
        self.waiting_state = AgentWaitingState()
        return messages


class MessageDeliveryProcessor:
    """Centralized processor that checks inboxes and delivers messages when conditions are met."""

    def __init__(self, agents_by_id: Dict[str, "BaseAgent"]):
        self.agents_by_id = agents_by_id
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the message delivery processor."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._delivery_loop())

    async def stop(self):
        """Stop the message delivery processor."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _delivery_loop(self):
        """Main delivery loop that checks conditions and delivers messages."""
        while self._running:
            try:
                # Check each agent's inbox
                for agent_id, agent in self.agents_by_id.items():
                    if (
                        hasattr(agent, "inbox")
                        and agent.inbox.check_delivery_condition()
                    ):
                        # Deliver all messages to this agent
                        messages = agent.inbox.get_all_messages()
                        if messages:
                            await self._deliver_messages_to_agent(agent, messages)

                # Sleep briefly to avoid busy waiting
                await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but don't crash the processor
                print(f"Message delivery error: {e}")
                await asyncio.sleep(1.0)

    async def _deliver_messages_to_agent(
        self, agent: "BaseAgent", messages: List[AgentMessage]
    ):
        """Deliver a batch of messages to an agent."""
        # Process structured messages like meeting invitations
        for message in messages:
            if hasattr(agent, "_handle_structured_message"):
                await agent._handle_structured_message(message)

        # Set delivery event to wake up any waiting WaitForMessage calls
        if hasattr(agent, "_message_delivery_event"):
            agent._delivered_messages = messages
            agent._message_delivery_event.set()
