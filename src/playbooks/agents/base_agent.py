import asyncio
import re
import uuid
from abc import ABC
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from playbooks.constants import EOM
from playbooks.enums import LLMMessageRole
from playbooks.meetings import MeetingMessageHandler
from playbooks.message_system import AgentMessage, SimplifiedInbox, WaitingMode
from playbooks.utils.spec_utils import SpecUtils

if TYPE_CHECKING:
    from src.playbooks.program import Program


# Legacy InboxManager class removed - replaced by SimplifiedInbox


class AgentCommunicationMixin:
    def __init__(self):
        self.program: Program | None = None
        self.inbox = SimplifiedInbox()
        self._message_delivery_event = asyncio.Event()
        self._delivered_messages: List[AgentMessage] = []

    async def SendMessage(self, target_agent_id: str, message: str):
        target_agent = self.program.agents_by_id.get(target_agent_id)
        current_frame = self.state.call_stack.peek()
        if current_frame:
            if target_agent:
                target_agent_name = str(target_agent)
            else:
                target_agent_name = BaseAgent.unknown_agent_str(target_agent_id)
            current_frame.add_uncached_llm_message(
                f"I {str(self)} sent message to {target_agent_name}: {message}",
                role=LLMMessageRole.ASSISTANT,
            )

        await self.program.route_message(self.id, target_agent_id, message)

    async def WaitForMessage(self, source_agent_id: str) -> str | None:
        """Wait for messages from a specific agent using the simplified system."""
        # Keep collecting messages until we get EOM
        collected_messages = []

        while True:
            # Set waiting mode for this iteration - WAITING_AGENT works for all agents including human
            self.inbox.set_waiting_mode(
                WaitingMode.WAITING_AGENT, target_agent_id=source_agent_id
            )

            # Wait for message delivery
            self._message_delivery_event.clear()
            await self._message_delivery_event.wait()

            # Process delivered messages
            messages = self._delivered_messages
            self._delivered_messages = []

            # Filter messages from the target agent
            relevant_messages = [
                msg for msg in messages if msg.sender_id == source_agent_id
            ]

            for agent_msg in relevant_messages:
                # Check for EOM - this signals end of message sequence
                if agent_msg.content == EOM:
                    # Process all collected messages and return
                    return self._process_collected_messages(
                        source_agent_id, collected_messages
                    )

                # Handle special message types (meeting invites, etc.)
                if await self._handle_structured_message(agent_msg):
                    continue

                # Collect regular messages
                collected_messages.append(agent_msg)

            # Continue waiting for more messages until EOM is received

    def _process_collected_messages(
        self, source_agent_id: str, collected_messages: List[AgentMessage]
    ) -> str:
        """Process a batch of collected messages and return formatted result."""
        processed_messages = []

        for agent_msg in collected_messages:
            self.state.session_log.append(
                f"Received message from {source_agent_id}: {agent_msg.content}"
            )
            current_frame = self.state.call_stack.peek()
            if current_frame:
                source_agent = self.program.agents_by_id.get(source_agent_id)
                if source_agent:
                    source_agent_name = str(source_agent)
                else:
                    source_agent_name = BaseAgent.unknown_agent_str(source_agent_id)
                current_frame.add_uncached_llm_message(
                    f"{source_agent_name} said to me {str(self)}: {agent_msg.content}",
                    role=LLMMessageRole.ASSISTANT,
                )

            processed_messages.append(agent_msg.content)

        return "\n".join(processed_messages)

    async def WaitForMeetingMessages(
        self, meeting_id: Optional[str] = None, timeout_seconds: float = 30.0
    ) -> str:
        """Wait for meeting messages using the simplified system."""
        # Determine which meeting to wait for
        if meeting_id is None:
            meeting_id = self.state.get_current_meeting()
            if meeting_id is None:
                return "Error: Not currently in a meeting"

        # Check if meeting exists
        meeting_owner = self.program.find_meeting_owner(meeting_id)
        if not meeting_owner:
            return f"Error: Meeting {meeting_id} not found"

        # Set waiting mode for this meeting
        self.inbox.set_waiting_mode(
            WaitingMode.WAITING_MEETING,
            target_meeting_id=meeting_id,
            timeout_seconds=5.0,  # 5-second batch timeout
        )

        # Wait for message delivery
        self._message_delivery_event.clear()
        await self._message_delivery_event.wait()

        # Process delivered messages
        messages = self._delivered_messages
        self._delivered_messages = []

        # Filter meeting-related messages
        meeting_messages = [
            msg
            for msg in messages
            if msg.meeting_id == meeting_id or msg.message_type == "meeting_message"
        ]

        if not meeting_messages:
            return "Meeting timeout - no messages received"

        # Add messages to LLM context
        if self.state.call_stack.frames:
            current_frame = self.state.call_stack.frames[-1]
            for msg in meeting_messages:
                current_frame.add_uncached_llm_message(
                    f"Meeting message: {msg.content}", LLMMessageRole.USER
                )

        # Return formatted messages
        if len(meeting_messages) == 1:
            return meeting_messages[0].content
        else:
            return "\n".join(
                f"Message {i+1}: {msg.content}"
                for i, msg in enumerate(meeting_messages)
            )

    async def InviteToMeeting(self, meeting_id: str, attendees: list):
        # Handle "meeting " prefix if present
        if SpecUtils.is_meeting_spec(meeting_id):
            meeting_id = SpecUtils.extract_meeting_id(meeting_id)

        if meeting_id in self.state.owned_meetings:
            meeting = self.state.owned_meetings[meeting_id]
            for attendee in attendees:
                # if already a participant, don't invite again
                if (
                    meeting.participants.get(SpecUtils.extract_agent_id(attendee))
                    is not None
                ):
                    continue

                # if already invited, don't invite again
                if attendee in meeting.pending_invitations:
                    continue

                # send invitation
                await self._send_invitation(meeting_id, attendee)

        else:
            return f"I {str(self)} don't own meeting {meeting_id}, so cannot invite {attendees} to it"

    def _format_meeting_messages(self, messages) -> str:
        """Format a list of meeting messages for display.

        Args:
            messages: List of Message objects

        Returns:
            Formatted string representation
        """
        if not messages:
            return "No messages"

        formatted = []
        for msg in messages:
            formatted.append(f"{msg.sender_type}: {msg.content}")

        return "\n".join(formatted)

    # Meeting message distribution using centralized MessageDeliveryProcessor

    async def _distribute_meeting_messages(self):
        """Simplified meeting message distribution using centralized message system."""
        for meeting_id, meeting in self.state.owned_meetings.items():
            # Check each participant for unsent messages
            for participant_id, participant_type in meeting.participants.items():
                last_sent_index = meeting.agent_last_message_index.get(
                    participant_id, -1
                )

                # Check if there are unsent messages
                if len(meeting.message_history) > last_sent_index + 1:
                    # Send new messages as structured AgentMessage objects
                    for i in range(last_sent_index + 1, len(meeting.message_history)):
                        msg = meeting.message_history[i]
                        # Don't send participant's own messages back to them
                        if msg.sender_id != participant_id:
                            await self.program.route_message(
                                self.id,
                                participant_id,
                                msg.content,
                                message_type="meeting_message",
                                meeting_id=meeting_id,
                            )

                    # Update last sent index
                    meeting.agent_last_message_index[participant_id] = (
                        len(meeting.message_history) - 1
                    )

    async def _handle_meeting_message(self, sender_id: str, message: str) -> bool:
        """Handle messages that might be meeting participant messages. Returns True if handled."""
        if not message.startswith("MEETING:"):
            return False

        # Only meeting owners should receive meeting messages
        if not hasattr(self, "state") or not hasattr(self.state, "owned_meetings"):
            return False

        try:
            # Parse: "MEETING:meeting_id:escaped_content"
            parts = message.split(":", 2)
            if len(parts) != 3:
                return False

            meeting_id = parts[1]
            escaped_content = parts[2]

            # Verify this is a meeting I own
            if meeting_id not in self.state.owned_meetings:
                if hasattr(self.state, "session_log"):
                    self.state.session_log.append(
                        f"Ignored meeting message for meeting {meeting_id} - not owned by me"
                    )
                return False

            meeting = self.state.owned_meetings[meeting_id]

            # Verify sender is a participant in this meeting
            if sender_id not in meeting.participants:
                if hasattr(self.state, "session_log"):
                    self.state.session_log.append(
                        f"Ignored spoofed meeting message from {sender_id} for meeting {meeting_id}"
                    )
                return False

            # Unescape the content (only at beginning)
            actual_content = re.sub(r"^~~MEETING:", "MEETING:", escaped_content)

            # Create message object and add to meeting history
            from datetime import datetime

            from playbooks.execution_state import Message

            # Get sender type from meeting participants
            sender_type = meeting.participants[sender_id]

            msg = Message(
                sender_id=sender_id,
                sender_type=sender_type,
                content=actual_content,
                timestamp=datetime.now(),
                meeting_id=meeting_id,
            )
            meeting.message_history.append(msg)

            if hasattr(self.state, "session_log"):
                self.state.session_log.append(
                    f"Added meeting message from {sender_id} to meeting {meeting_id}: {actual_content}"
                )

            # Get current call stack frame to add messages
            if self.state.call_stack.frames:
                current_frame = self.state.call_stack.frames[-1]
                current_frame.add_uncached_llm_message(
                    f"In meeting {meeting_id}, agent {sender_id} said: {actual_content}",
                    LLMMessageRole.ASSISTANT,
                )

            return True

        except Exception as e:
            if hasattr(self, "state") and hasattr(self.state, "session_log"):
                self.state.session_log.append(f"Error processing meeting message: {e}")
            return False

    # Background processing methods removed - replaced by centralized MessageDeliveryProcessor

    async def _handle_structured_message(self, agent_msg: AgentMessage) -> bool:
        """Handle structured message types like meeting invites.

        Args:
            agent_msg: The AgentMessage object to handle

        Returns:
            True if the message was handled as a special type, False otherwise
        """
        if agent_msg.message_type == "meeting_invite":
            # Handle meeting invitation
            await self._process_meeting_invitation(
                agent_msg.sender_id, agent_msg.meeting_id, agent_msg.content
            )
            return True
        elif agent_msg.message_type == "meeting_response":
            # Handle meeting join/reject responses
            return await self._handle_meeting_response(agent_msg)

        # Not a special message type
        return False

    async def _handle_meeting_response(self, agent_msg: AgentMessage) -> bool:
        """Handle meeting join/reject responses."""
        if (
            not agent_msg.meeting_id
            or agent_msg.meeting_id not in self.state.owned_meetings
        ):
            return False

        meeting = self.state.owned_meetings[agent_msg.meeting_id]
        agent = self.program.agents_by_id.get(agent_msg.sender_id)

        if (
            "accepted" in agent_msg.content.lower()
            or "joined" in agent_msg.content.lower()
        ):
            # Agent joined the meeting
            meeting.participants[agent_msg.sender_id] = agent.klass
            meeting.agent_last_message_index[agent_msg.sender_id] = -1
            self.state.session_log.append(
                f"Agent {agent_msg.sender_id} joined meeting {agent_msg.meeting_id}"
            )
        elif "rejected" in agent_msg.content.lower():
            # Agent rejected the meeting
            self.state.session_log.append(
                f"Agent {agent_msg.sender_id} rejected meeting {agent_msg.meeting_id}"
            )

        # Remove pending invitation
        invitation_specs_to_remove = []
        for agent_spec in meeting.pending_invitations:
            if agent_msg.sender_id in agent_spec or agent_spec == agent_msg.sender_id:
                invitation_specs_to_remove.append(agent_spec)

        for agent_spec in invitation_specs_to_remove:
            meeting.pending_invitations.discard(agent_spec)

        return True

    async def _handle_special_message(self, source_agent_id: str, message: str) -> bool:
        """Handle special message types automatically.

        Args:
            source_agent_id: ID of the agent that sent the message
            message: The message content

        Returns:
            True if the message was handled as a special type, False otherwise
        """
        # Handle JOINED responses
        match = re.match(r"^JOINED meeting (\d+):", message)
        if match:
            meeting_id = match.group(1)
            agent = self.program.agents_by_id.get(source_agent_id)
            if not agent:
                raise ValueError(f"Agent {source_agent_id} not found")

            if meeting_id in self.state.owned_meetings:
                meeting = self.state.owned_meetings[meeting_id]
                meeting.participants[source_agent_id] = agent.klass
                meeting.agent_last_message_index[source_agent_id] = -1
                self.state.session_log.append(
                    f"Agent {source_agent_id} joined my meeting {meeting_id}"
                )

                # Remove pending invitation from meeting
                invitation_specs_to_remove = []
                for agent_spec in meeting.pending_invitations:
                    if source_agent_id in agent_spec or agent_spec == source_agent_id:
                        invitation_specs_to_remove.append(agent_spec)

                for agent_spec in invitation_specs_to_remove:
                    meeting.pending_invitations.discard(agent_spec)
                return True
            return False

        # Handle REJECTED responses
        match = re.match(r"^REJECTED meeting (\d+):", message)
        if match:
            meeting_id = match.group(1)
            # Remove pending invitation from meeting if we own it
            if meeting_id in self.state.owned_meetings:
                meeting = self.state.owned_meetings[meeting_id]
                invitation_specs_to_remove = []
                for agent_spec in meeting.pending_invitations:
                    if source_agent_id in agent_spec or agent_spec == source_agent_id:
                        invitation_specs_to_remove.append(agent_spec)

                for agent_spec in invitation_specs_to_remove:
                    meeting.pending_invitations.discard(agent_spec)

                self.state.session_log.append(
                    f"Agent {source_agent_id} rejected meeting {meeting_id}"
                )
                return True
            return False

        # Handle ENDED meeting messages
        match = re.match(r"^ENDED meeting (\d+):", message)
        if match:
            meeting_id = match.group(1)
            if meeting_id in self.state.owned_meetings:
                self.state.session_log.append(f"Meeting {meeting_id} has ended")
                return True
            return False

        # Handle INVITATION messages
        match = re.match(r"^INVITATION for meeting (\d+):(.*)$", message)
        if match:
            meeting_id = match.group(1)
            topic = match.group(2) if match.group(2) else "Meeting"

            # Process the invitation
            await self._process_meeting_invitation(source_agent_id, meeting_id, topic)
            return True

        # Not a special message
        return False

    async def _process_meeting_invitation(
        self, inviter_id: str, meeting_id: str, topic: str
    ):
        """Process a meeting invitation. Default implementation rejects all invitations.

        Subclasses should override this method to implement their invitation handling logic.

        Args:
            inviter_id: ID of the agent that sent the invitation
            meeting_id: ID of the meeting
            topic: Topic/description of the meeting
        """
        # Default implementation - reject invitation
        self.state.session_log.append(
            f"Received meeting invitation {meeting_id} from {inviter_id} for '{topic}' - rejecting (no handler)"
        )

        # Send structured rejection response
        await self.program.route_message(
            self.id,
            inviter_id,
            "Meeting invitation rejected: No meeting handler available",
            message_type="meeting_response",
            meeting_id=meeting_id,
        )


class BaseAgent(AgentCommunicationMixin, ABC):
    """
    Abstract base class for all agent implementations.

    Agents are entities that can process messages and generate responses. This class
    defines the common interface that all agent implementations must adhere to.

    Attributes:
        klass: A string identifier for the agent class/type.
    """

    def __init__(self, klass: str, agent_id: str = None):
        """
        Initialize a new BaseAgent.

        Args:
            klass: The class/type identifier for this agent.
            agent_id: Optional agent ID. If not provided, will generate UUID (for backward compatibility).
        """
        super().__init__()
        self.id = agent_id if agent_id is not None else str(uuid.uuid4())
        self.klass = klass
        self.kwargs = {}

        # Initialize meeting message handler
        self.meeting_message_handler = MeetingMessageHandler(self.id, self.klass)

    async def begin(self):
        pass

    async def initialize(self):
        pass

    async def start_streaming_say(self, recipient=None):
        """Start displaying a streaming Say() message. Override in subclasses."""
        pass

    async def stream_say_update(self, content: str):
        """Add content to the current streaming Say() message. Override in subclasses."""
        pass

    async def complete_streaming_say(self):
        """Complete the current streaming Say() message. Override in subclasses."""
        pass

    @staticmethod
    def unknown_agent_str(agent_id: str):
        return f"Agent (agent {agent_id})"

    def to_dict(self) -> Dict[str, Any]:
        return {**self.kwargs, "type": self.klass, "agent_id": self.id}
