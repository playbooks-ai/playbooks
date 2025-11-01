"""
MessagingMixin for event-driven message processing.
"""

import asyncio
from typing import List

from ..async_message_queue import AsyncMessageQueue
from ..constants import EOM, EXECUTION_FINISHED
from ..debug_logger import debug
from ..exceptions import ExecutionFinished
from ..llm_messages import AgentCommunicationLLMMessage
from ..message import Message


class MessagingMixin:
    """Mixin for event-driven message processing functionality."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._message_queue = AsyncMessageQueue()
        self._message_buffer: List[Message] = []

    async def _add_message_to_buffer(self, message) -> None:
        """Add a message to buffer and notify waiting processes.

        This is the single entry point for all incoming messages.
        """
        if hasattr(self, "meeting_manager") and self.meeting_manager:
            debug(f"{str(self)}: Adding message to meeting manager: {message}")
            message_handled = await self.meeting_manager._add_message_to_buffer(message)
            if message_handled:
                return

        debug(f"{str(self)}: Adding message to queue: {message}")
        await self._message_queue.put(message)
        self._message_buffer.append(message)

    async def WaitForMessage(self, wait_for_message_from: str) -> List[Message]:
        """Wait for messages with event-driven delivery and differential timeouts.

        Args:
            wait_for_message_from: Message source - "*", "human", "agent 1234", or "meeting 123"

        Returns:
            List of Message objects
        """
        debug(f"{str(self)}: Waiting for message from {wait_for_message_from}")

        if self.program.execution_finished:
            raise ExecutionFinished(EXECUTION_FINISHED)

        # Determine timeout based on context
        if wait_for_message_from.startswith("meeting "):
            # For meetings, use differential timeout logic
            timeout = await self._get_meeting_timeout(wait_for_message_from)
        else:
            # For direct messages (human/agent), release immediately
            timeout = 5.0

        # Create predicate for message filtering
        def message_predicate(message: Message) -> bool:
            # Always match EOM
            if message.content == EOM:
                return True

            # Match based on source specification
            if wait_for_message_from == "*":
                return True
            elif wait_for_message_from in ("human", "user"):
                return message.sender_id in ("human", "user")
            elif wait_for_message_from.startswith("meeting "):
                # Extract meeting ID
                meeting_id = wait_for_message_from.split(" ", 1)[1]
                return message.meeting_id == meeting_id
            elif wait_for_message_from.startswith("agent "):
                agent_id = wait_for_message_from.split(" ", 1)[1]
                return message.sender_id == agent_id
            else:
                return message.sender_id == wait_for_message_from

        # Use queue's get_batch for event-driven waiting
        try:
            messages = await self._message_queue.get_batch(
                predicate=message_predicate,
                timeout=timeout,
                min_messages=1,
                max_messages=100,
            )

            # Process and return messages
            if messages:
                return await self._process_collected_messages_from_queue(messages)
            else:
                # Timeout with no messages - return empty list
                return []

        except asyncio.TimeoutError:
            debug(f"{str(self)}: Timeout waiting for messages")
            return []

    async def _get_meeting_timeout(self, meeting_spec: str) -> float:
        """Determine timeout for meeting messages based on agent targeting.

        Returns:
            0.5s if agent is targeted (immediate response), 5.0s for passive listening
        """
        # Check if there are any messages in queue targeting this agent
        targeted_message = await self._message_queue.peek(
            lambda m: (
                m.meeting_id == meeting_spec.split(" ", 1)[1]
                and (
                    # Explicitly targeted via target_agent_ids
                    (m.target_agent_ids and self.id in m.target_agent_ids)
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

        Args:
            messages: List of messages from the queue

        Returns:
            List of Message objects (EOM filtered out)
        """
        debug(f"{str(self)}: Processing {len(messages)} messages from queue")

        if not messages:
            return []

        # Filter out EOM messages before processing
        messages = [msg for msg in messages if msg.content != EOM]

        if not messages:
            return []

        # Sync with _message_buffer (used by agent_chat.py)
        for msg in messages:
            if msg in self._message_buffer:
                self._message_buffer.remove(msg)

        if not self.state.call_stack.is_empty():
            messages_str = []
            for message in messages:
                messages_str.append(
                    f"Received message from {message.sender_klass}(agent {message.sender_id}): {message.content}"
                )
            debug(f"{str(self)}: Messages to process: {messages_str}")
            # Use the first sender agent for the semantic message type
            sender_agent = messages[0].sender_klass if messages else None
            agent_comm_msg = AgentCommunicationLLMMessage(
                "\n".join(messages_str),
                sender_agent=sender_agent,
                target_agent=self.klass,
            )
            self.state.call_stack.add_llm_message(agent_comm_msg)

        return messages
