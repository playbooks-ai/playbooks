"""
MessagingMixin for event-driven message processing.
"""

import asyncio
import time
from typing import List

from ..constants import EOM, EXECUTION_FINISHED
from ..exceptions import ExecutionFinished
from ..llm_messages import AgentCommunicationLLMMessage
from ..message import Message


class MessagingMixin:
    """Mixin for event-driven message processing functionality."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._message_buffer: List[Message] = []
        self._message_event = asyncio.Event()

    async def _add_message_to_buffer(self, message) -> None:
        """Add a message to buffer and notify waiting processes.

        This is the single entry point for all incoming messages.
        """
        if hasattr(self, "meeting_manager") and self.meeting_manager:
            message_handled = await self.meeting_manager._add_message_to_buffer(message)
            if message_handled:
                return

        # Regular messages go to buffer
        self._message_buffer.append(message)
        # Wake up any agents waiting for messages
        self._message_event.set()

    async def WaitForMessage(self, wait_for_message_from: str) -> List[Message]:
        """Unified message waiting with smart buffering.

        Args:
            wait_for_message_from: Message source - "*", "human", "agent 1234", or "meeting 123"

        Returns:
            Collected messages as string
        """
        while True:
            if self.program.execution_finished:
                raise ExecutionFinished(EXECUTION_FINISHED)

            first_message_time = None
            buffer_timeout = 5.0  # 5s maximum buffer time

            release_buffer = False
            num_messages_to_process = 0
            # Check buffer for messages
            for message in self._message_buffer:
                # Track timing from first message
                if first_message_time is None:
                    first_message_time = message.created_at.timestamp()

                # Check if we should release the buffer
                if release_buffer or self._should_release_buffer(
                    wait_for_message_from, message, first_message_time, buffer_timeout
                ):
                    release_buffer = True
                    num_messages_to_process += 1

                if message.content == EOM:
                    release_buffer = True
                    break
            if release_buffer:
                return await self._process_collected_messages(num_messages_to_process)

            # Wait for new messages or timeout
            try:
                await asyncio.wait_for(self._message_event.wait(), timeout=5)
                self._message_event.clear()
            except asyncio.TimeoutError:
                # Loop back to process received messages
                pass

    def _should_release_buffer(
        self,
        source: str,
        message: Message,
        first_message_time: float,
        buffer_timeout: float,
    ) -> bool:
        """Determine if we should release the buffer now.

        Args:
            source: The source we're waiting for ("human", "agent 1234", "meeting 123")
            message: The message that just arrived
            first_message_time: When we started buffering
            buffer_timeout: Maximum buffer time (5s)

        Returns:
            True if buffer should be released now
        """
        time_elapsed = time.time() - first_message_time if first_message_time else 0

        if source.startswith("meeting "):
            # if the message mentions me, release immediately
            if self.id.lower() in message.content.lower():
                return True

            if self.name.lower() in message.content.lower():
                return True

            # Meeting: always wait full 5s to accumulate chatter
            return time_elapsed >= buffer_timeout
        else:
            # Human/Agent: release immediately on target source OR 5s timeout
            target_source_message = (
                message.sender_id == source
                or message.sender_id == "human"
                or source == "*"
            )
            sent_directly_to_me = message.recipient_id == self.id
            if (
                target_source_message
                or sent_directly_to_me
                or message.content == EOM
                or time_elapsed >= buffer_timeout
            ):
                return True

    async def _process_collected_messages(
        self, num_messages_to_process: int = None
    ) -> List[Message]:
        """Process and format collected messages.

        Args:
            messages: List of message objects

        Returns:
            Formatted message string
        """
        if not num_messages_to_process:
            num_messages_to_process = len(self._message_buffer)

        if not num_messages_to_process:
            return ""

        # Filter out EOM messages before processing
        messages = [
            msg
            for msg in self._message_buffer[:num_messages_to_process]
            if msg.content != EOM
        ]

        # Remove processed messages from buffer
        self._message_buffer = self._message_buffer[num_messages_to_process:]

        if self.state.call_stack.is_empty():
            await self.execute_playbook("ProcessMessages", messages=messages)
        else:
            messages_str = []
            for message in messages:
                messages_str.append(
                    f"Received message from {message.sender_klass}(agent {message.sender_id}): {message.content}"
                )

            # Use the first sender agent for the semantic message type
            sender_agent = messages[0].sender_klass if messages else None
            agent_comm_msg = AgentCommunicationLLMMessage(
                "\n".join(messages_str),
                sender_agent=sender_agent,
                target_agent=self.klass,
            )
            self.state.call_stack.add_llm_message(agent_comm_msg)

        return messages
