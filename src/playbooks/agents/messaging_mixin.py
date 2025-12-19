"""
MessagingMixin for event-driven message processing.
"""

import asyncio
from typing import List, Optional

from playbooks.agents.async_queue import AsyncMessageQueue
from playbooks.core.constants import EOM, EXECUTION_FINISHED
from playbooks.core.events import MessageReceivedEvent, WaitForMessageEvent
from playbooks.core.exceptions import ExecutionFinished
from playbooks.core.identifiers import AgentID, MeetingID
from playbooks.core.message import Message, MessageType
from playbooks.infrastructure.logging.debug_logger import debug
from playbooks.llm.messages import AgentCommunicationLLMMessage


class MessagingMixin:
    """Mixin for event-driven message processing functionality."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._message_queue = AsyncMessageQueue()

    async def _add_message_to_buffer(self, message: Message) -> None:
        """Add a message to buffer and notify waiting processes.

        This is the single entry point for all incoming messages.
        Delegates to meeting manager if available, otherwise adds to message queue.

        Args:
            message: Message to add to buffer
        """
        if hasattr(self, "meeting_manager") and self.meeting_manager:
            debug(f"{str(self)}: Adding message to meeting manager: {message}")
            message_handled = await self.meeting_manager._add_message_to_buffer(message)
            if message_handled:
                return

        debug(f"{str(self)}: Adding message to queue: {message}")
        await self._message_queue.put(message)

        # Publish message received event for telemetry
        if hasattr(self, "event_bus") and hasattr(self, "program"):
            self.event_bus.publish(
                MessageReceivedEvent(
                    session_id=(
                        self.program.event_bus.session_id if self.program else ""
                    ),
                    agent_id=self.id,
                    message_id=message.id,
                    recipient_id=self.id,
                    recipient_klass=self.klass,
                    sender_id=(
                        message.sender_id.id
                        if hasattr(message.sender_id, "id")
                        else str(message.sender_id)
                    ),
                    sender_klass=message.sender_klass,
                )
            )

    async def WaitForMessage(
        self, wait_for_message_from: str, *, timeout: Optional[float] = None
    ) -> List[Message]:
        """Wait for messages with event-driven delivery and differential timeouts.

        Args:
            wait_for_message_from: Message source - "*", "human", "agent 1234", or "meeting 123"
            timeout: Optional timeout override in seconds. If provided, skips
                meeting differential timeouts and uses this exact value.

        Returns:
            List of Message objects
        """
        debug(
            f"{str(self)}: WaitForMessage STARTING - waiting for message from {wait_for_message_from}"
        )

        if self.program.execution_finished:
            raise ExecutionFinished(EXECUTION_FINISHED)

        # Determine timeout based on context, unless explicitly overridden
        if timeout is None:
            if wait_for_message_from.startswith("meeting "):
                # For meetings, use differential timeout logic
                timeout = await self._get_meeting_timeout(wait_for_message_from)
            else:
                # For direct messages (human/agent), release immediately
                timeout = 5.0

        debug(
            f"{str(self)}: WaitForMessage - using timeout={timeout}s for {wait_for_message_from}"
        )

        # Create predicate for message filtering
        def message_predicate(message: Message) -> bool:
            # Always match EOM
            if message.content == EOM:
                return True

            # Match based on source specification
            if wait_for_message_from == "*":
                # Exclude messages from meetings we've joined - those should only
                # be handled by meeting playbook's WaitForMessage calls
                if (
                    message.meeting_id
                    and hasattr(self, "joined_meetings")
                    and message.meeting_id.id in self.joined_meetings
                ):
                    return False
                return True
            elif wait_for_message_from in ("human", "user"):
                # Compare structured IDs
                return message.sender_id.id == "human"
            elif wait_for_message_from.startswith("meeting "):
                # Parse meeting spec and compare
                expected_meeting_id = MeetingID.parse(wait_for_message_from)
                return message.meeting_id == expected_meeting_id
            elif wait_for_message_from.startswith("agent "):
                # Parse agent spec and compare
                expected_agent_id = AgentID.parse(wait_for_message_from)
                return message.sender_id == expected_agent_id
            else:
                # Assume raw ID
                expected_agent_id = AgentID.parse(wait_for_message_from)
                return message.sender_id == expected_agent_id

        # Use queue's get_batch for event-driven waiting
        try:
            # Publish wait-start (observability; apps should subscribe instead of patching)
            if getattr(self, "program", None) and getattr(
                self.program, "event_bus", None
            ):
                self.program.event_bus.publish(
                    WaitForMessageEvent(
                        session_id=self.program.event_bus.session_id,
                        agent_id=getattr(self, "id", ""),
                        wait_for_message_from=wait_for_message_from,
                        timeout=timeout,
                        received_count=0,
                    )
                )

            debug(
                f"{str(self)}: WaitForMessage - calling get_batch with timeout={timeout}s..."
            )
            messages = await self._message_queue.get_batch(
                predicate=message_predicate,
                timeout=timeout,
                min_messages=1,
                max_messages=100,
            )

            # Process and return messages
            if messages:
                debug(
                    f"{str(self)}: WaitForMessage - RECEIVED {len(messages)} messages!"
                )
                if getattr(self, "program", None) and getattr(
                    self.program, "event_bus", None
                ):
                    self.program.event_bus.publish(
                        WaitForMessageEvent(
                            session_id=self.program.event_bus.session_id,
                            agent_id=getattr(self, "id", ""),
                            wait_for_message_from=wait_for_message_from,
                            timeout=timeout,
                            received_count=len(messages),
                        )
                    )
                return await self._process_collected_messages_from_queue(messages)
            else:
                debug(
                    f"{str(self)}: WaitForMessage - TIMEOUT with no messages after {timeout}s"
                )
                if getattr(self, "program", None) and getattr(
                    self.program, "event_bus", None
                ):
                    self.program.event_bus.publish(
                        WaitForMessageEvent(
                            session_id=self.program.event_bus.session_id,
                            agent_id=getattr(self, "id", ""),
                            wait_for_message_from=wait_for_message_from,
                            timeout=timeout,
                            received_count=0,
                        )
                    )
                # Timeout with no messages - return empty list
                return []

        except asyncio.TimeoutError:
            debug(f"{str(self)}: WaitForMessage - TIMEOUT exception after {timeout}s")
            if getattr(self, "program", None) and getattr(
                self.program, "event_bus", None
            ):
                self.program.event_bus.publish(
                    WaitForMessageEvent(
                        session_id=self.program.event_bus.session_id,
                        agent_id=getattr(self, "id", ""),
                        wait_for_message_from=wait_for_message_from,
                        timeout=timeout,
                        received_count=0,
                    )
                )
            return []

    async def _get_meeting_timeout(self, meeting_spec: str) -> float:
        """Determine timeout for meeting messages based on agent targeting.

        Uses differential timeout logic: shorter timeout if agent is explicitly
        targeted or mentioned in message content.

        Args:
            meeting_spec: Meeting specification (e.g., "meeting 123")

        Returns:
            0.5s if agent is targeted (immediate response), 5.0s for passive listening
        """
        # Parse meeting ID for comparison
        expected_meeting_id = MeetingID.parse(meeting_spec)
        my_agent_id = AgentID.parse(self.id)

        # Check if there are any messages in queue targeting this agent
        targeted_message = await self._message_queue.peek(
            lambda m: (
                m.meeting_id == expected_meeting_id
                and (
                    # Explicitly targeted via target_agent_ids
                    (m.target_agent_ids and my_agent_id in m.target_agent_ids)
                    # Or mentioned in content
                    or (self.id.lower() in m.content.lower())
                    or (
                        hasattr(self, "name") and self.name.lower() in m.content.lower()
                    )
                )
            )
        )

        if targeted_message:
            # Agent is targeted - respond immediately
            debug(f"{str(self)}: Targeted in meeting, using short timeout (0.5s)")
            return 0.5
        else:
            # Passive listening - accumulate chatter
            debug(f"{str(self)}: Passive listening in meeting, using long timeout (5s)")
            return 5.0

    async def _process_collected_messages_from_queue(
        self, messages: List[Message]
    ) -> List[Message]:
        """Process and format messages retrieved from AsyncMessageQueue.

        Always logs received messages as AgentCommunicationLLMMessage,
        adding to call stack frame if inside playbook or to top_level_llm_messages if not.

        Args:
            messages: List of messages from the queue (EOM already consumed by queue)

        Returns:
            List of Message objects
        """
        debug(f"{str(self)}: Processing {len(messages)} messages from queue")

        if not messages:
            return []

        # Always create agent communication message for received messages
        messages_str = []
        for i, message in enumerate(messages):
            message_type_str = ""
            if message.message_type == MessageType.MEETING_INVITATION:
                message_type_str = (
                    f" [MEETING_INVITATION for meeting {message.meeting_id.id}]"
                    if message.meeting_id
                    else ""
                )
            elif message.message_type == MessageType.MEETING_BROADCAST:
                message_type_str = (
                    f" [in meeting {message.meeting_id.id}]"
                    if message.meeting_id
                    else ""
                )

            formatted_msg = f"Received message from {message.sender_klass}({message.sender_id.id}){message_type_str}: {message.content}"
            messages_str.append(formatted_msg)
        debug(f"{str(self)}: Messages to process: {messages_str}")

        joined_str = "\n".join(messages_str)

        # Use the first sender agent for the semantic message type
        sender_agent = messages[0].sender_klass if messages else None
        agent_comm_msg = AgentCommunicationLLMMessage(
            joined_str,
            sender_agent=sender_agent,
            target_agent=self.klass,
        )

        # Add to call stack (handles both frame and top-level message cases)
        self.call_stack.add_llm_message(agent_comm_msg)

        return messages
