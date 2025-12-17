"""Meeting management functionality for AI agents."""

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol

from playbooks.agents.ai_agent import AIAgent
from playbooks.agents.human_agent import HumanAgent
from playbooks.agents.local_ai_agent import LocalAIAgent
from playbooks.config import config
from playbooks.core.exceptions import KlassNotFoundError
from playbooks.core.identifiers import AgentID, MeetingID
from playbooks.core.message import Message, MessageType
from playbooks.debug.debug_handler import debug
from playbooks.llm.messages import MeetingLLMMessage, SessionLogLLMMessage
from playbooks.meetings.meeting import (
    JoinedMeeting,
    Meeting,
    MeetingInvitation,
    MeetingInvitationStatus,
)
from playbooks.meetings.meeting_message_handler import MeetingMessageHandler
from playbooks.playbook import LLMPlaybook, Playbook

if TYPE_CHECKING:
    from playbooks.agents.base_agent import BaseAgent
    from playbooks.program import Program

logger = logging.getLogger(__name__)


class RollingMessageCollector:
    """Collects messages with a rolling timeout to minimize thrashing.

    When a message is received, starts a timeout. If another message arrives
    before timeout, collects it and resets the timer. When timeout expires
    without new messages, delivers all collected messages.

    Implements absolute maximum wait time to prevent starvation: if messages
    keep arriving continuously, the oldest message will still be delivered
    within max_batch_wait seconds.
    """

    def __init__(
        self,
        timeout_seconds: float = 2.0,
        max_batch_wait: float = 10.0,
        task_factory=None,
    ):
        """Initialize the collector.

        Args:
            timeout_seconds: Rolling timeout duration in seconds (default 2.0)
            max_batch_wait: Absolute maximum wait for oldest message (default 10.0)
            task_factory: Optional factory function for creating background tasks (default: asyncio.create_task)
        """
        self.timeout_seconds = timeout_seconds
        self.max_batch_wait = max_batch_wait
        self.buffer: List[Message] = []
        self.timer_task: Optional[asyncio.Task] = None
        self.delivery_callback = None
        self._lock = asyncio.Lock()
        self.first_message_time: Optional[float] = None
        self._timer_seq = (
            0  # Monotonically increasing sequence to invalidate old timers
        )
        self._task_factory = task_factory or asyncio.create_task
        self._background_tasks: set = set()

    async def add_message(self, message: Message) -> None:
        """Add a message to the buffer and reset the rolling timeout.

        Args:
            message: Message to add to the buffer
        """
        async with self._lock:
            # Track when first message arrived for absolute max wait enforcement
            if not self.buffer:
                self.first_message_time = asyncio.get_event_loop().time()

            # Add message to buffer
            self.buffer.append(message)

            # Check if we've exceeded absolute maximum wait time
            if self.first_message_time:
                elapsed = asyncio.get_event_loop().time() - self.first_message_time
                if elapsed >= self.max_batch_wait:
                    # Force immediate delivery
                    if len(self.buffer) > 0:
                        await self._deliver_now()
                    return

            # Decide whether to reset the timer based on elapsed time
            # Don't reset timer if we're past half the max_batch_wait to ensure delivery
            should_reset_timer = True
            if self.first_message_time:
                elapsed = asyncio.get_event_loop().time() - self.first_message_time
                # If we've waited more than half of max_batch_wait, don't reset timer
                # This ensures messages don't wait indefinitely due to rolling resets
                if elapsed >= (self.max_batch_wait / 2):
                    should_reset_timer = False

            # Cancel existing timer if any (unless we're close to max wait)
            if should_reset_timer:
                if self.timer_task and not self.timer_task.done():
                    # Just cancel, don't await - the task will clean up asynchronously
                    # Awaiting would cause deadlock since timer tries to acquire this same lock
                    self.timer_task.cancel()
                # Always start a new timer on reset (don't rely on .done() immediately after cancel)
                self._timer_seq += 1
                self.timer_task = self._task_factory(
                    self._timer_expired(self._timer_seq)
                )
                self._background_tasks.add(self.timer_task)
                self.timer_task.add_done_callback(self._background_tasks.discard)
            else:
                # Ensure there is a timer running (but don't reset it)
                if not self.timer_task or self.timer_task.done():
                    self._timer_seq += 1
                    self.timer_task = self._task_factory(
                        self._timer_expired(self._timer_seq)
                    )
                    self._background_tasks.add(self.timer_task)
                    self.timer_task.add_done_callback(self._background_tasks.discard)

        # Yield control OUTSIDE the lock to ensure timer task can be scheduled
        await asyncio.sleep(0)

    async def flush(self) -> None:
        """Immediately deliver all buffered messages, canceling any pending timer.

        Called before prompt construction to ensure all agent communications
        are included in the LLM context.
        """
        async with self._lock:
            if len(self.buffer) > 0:
                # Cancel pending timer
                if self.timer_task and not self.timer_task.done():
                    # Just cancel, don't await - would cause deadlock
                    self.timer_task.cancel()
                    self._timer_seq += 1

                # Deliver immediately
                await self._deliver_now()
            else:
                debug("RollingMessageCollector: flush() called but buffer is empty")

    async def _timer_expired(self, timer_seq: int) -> None:
        """Called when the rolling timeout expires without new messages."""
        try:
            await asyncio.sleep(self.timeout_seconds)

            # Acquire lock to safely extract and clear buffer
            async with self._lock:
                if timer_seq != self._timer_seq:
                    return
                if not self.buffer:
                    return

                await self._deliver_now()
        except asyncio.CancelledError:
            pass  # Timer was cancelled, waiting for more messages

    async def _deliver_now(self) -> None:
        """Deliver buffered messages immediately.

        Must be called while holding self._lock or from within a locked context.
        """
        # Invalidate any existing timer (whether cancelled or racing to expire).
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
        self._timer_seq += 1
        self.timer_task = None

        if self.buffer and self.delivery_callback:
            message_count = len(self.buffer)
            messages = self.buffer.copy()
            wait_time = None
            if self.first_message_time:
                wait_time = asyncio.get_event_loop().time() - self.first_message_time
            self.buffer.clear()
            self.first_message_time = None

            if wait_time:
                debug(
                    f"RollingMessageCollector: _deliver_now() delivering {message_count} messages after {wait_time:.2f}s wait"
                )
            else:
                debug(
                    f"RollingMessageCollector: _deliver_now() delivering {message_count} messages"
                )

            # Deliver messages outside the lock to avoid deadlock
            delivery_task = self._task_factory(self.delivery_callback(messages))
            self._background_tasks.add(delivery_task)
            delivery_task.add_done_callback(self._background_tasks.discard)
            debug(
                f"RollingMessageCollector: _deliver_now() created delivery task (id={id(delivery_task)})"
            )
        elif not self.buffer:
            debug("RollingMessageCollector: _deliver_now() called but buffer is empty")
        elif not self.delivery_callback:
            debug(
                "RollingMessageCollector: _deliver_now() called but no delivery callback set!"
            )

    def set_delivery_callback(self, callback) -> None:
        """Set the callback to call when messages should be delivered.

        Args:
            callback: Async function that takes a list of messages
        """
        self.delivery_callback = callback

    async def cleanup(self) -> None:
        """Clean up background tasks."""
        # Cancel all background tasks
        for task in self._background_tasks.copy():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    # Ignore other exceptions during cleanup
                    pass
            self._background_tasks.discard(task)


class PlaybookExecutor(Protocol):
    """Protocol for executing playbooks."""

    playbooks: Dict[str, Playbook]

    async def execute_playbook(
        self, name: str, args: List[Any] = None, kwargs: Dict[str, Any] = None
    ) -> Any:
        """Execute a playbook by name."""
        ...


class MeetingManager:
    """Manages meeting-related functionality for AI agents.

    Uses dependency injection for clean separation of concerns:
    - agent_id, agent_klass: Simple identity data
    - state: AIAgent instance for accessing state and session tracking
    - program: Program instance for message routing and agent lookup
    - playbook_executor: Protocol for executing playbooks
    """

    def __init__(
        self,
        agent_id: str,
        agent_klass: str,
        agent: "AIAgent",
        program: "Program",
        playbook_executor: PlaybookExecutor,
    ):
        """Initialize meeting manager with injected dependencies.

        Args:
            agent_id: The agent's unique identifier
            agent_klass: The agent's class/type
            agent: AIAgent instance for accessing state and sessions
            program: Program instance for routing and lookups
            playbook_executor: Protocol implementation for playbook execution
        """
        self.agent_id = agent_id
        self.agent_klass = agent_klass
        self.agent = agent
        self.program = program
        self.playbook_executor = playbook_executor

        self.meeting_message_handler = MeetingMessageHandler(
            self.agent_id, self.agent_klass
        )

        # Initialize rolling message collector with config timeouts
        self.message_collector = RollingMessageCollector(
            timeout_seconds=config.meeting_message_batch_timeout,
            max_batch_wait=config.meeting_message_batch_max_wait,
            task_factory=self._create_background_task,
        )
        self.message_collector.set_delivery_callback(self._deliver_collected_messages)

        # Track background tasks for proper cleanup
        self._background_tasks: set = set()

    async def cleanup(self) -> None:
        """Clean up background tasks and resources."""
        # Cancel all background tasks
        for task in self._background_tasks.copy():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    # Ignore other exceptions during cleanup
                    pass
            self._background_tasks.discard(task)

        # Clean up message collector
        if self.message_collector:
            await self.message_collector.flush()

    def _create_background_task(self, coro) -> asyncio.Task:
        """Create a background task and track it for cleanup."""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        # Remove task from tracking when it completes
        task.add_done_callback(self._background_tasks.discard)
        return task

    def ensure_meeting_playbook_kwargs(self, playbooks: Dict[str, Any]) -> None:
        """Ensure that all meeting playbooks have the required kwargs.

        Args:
            playbooks: Dictionary of playbooks to process
        """
        for playbook in playbooks.values():
            if playbook.meeting and isinstance(playbook, LLMPlaybook):
                signature = playbook.signature

                # Check if topic and attendees are missing
                missing_params = []
                if "topic:" not in signature and "topic :" not in signature:
                    missing_params.append("topic: str")
                if "attendees:" not in signature and "attendees :" not in signature:
                    missing_params.append("attendees: List[str]")

                if missing_params:
                    # Find the position to insert parameters (before the closing parenthesis)
                    # Handle cases like "GameRoom() -> None" or "TaxPrepMeeting($form: str) -> None"
                    if ") ->" in signature:
                        # Has return type annotation
                        before_return = signature.split(") ->")[0]
                        after_return = ") ->" + signature.split(") ->", 1)[1]
                    else:
                        # No return type, just ends with )
                        before_return = signature.rstrip(")")
                        after_return = ")"

                    # Check if there are existing parameters
                    if before_return.endswith("("):
                        # No existing parameters, add directly
                        new_params = ", ".join(missing_params)
                    else:
                        # Has existing parameters, add with comma prefix
                        new_params = ", " + ", ".join(missing_params)

                    # Reconstruct the signature
                    playbook.signature = before_return + new_params + after_return

    # def get_meeting_playbooks(self, playbooks: Dict[str, Playbook]) -> List[str]:
    #     """Get list of meeting playbook names.

    #     Args:
    #         playbooks: Dictionary of available playbooks

    #     Returns:
    #         List of playbook names that are marked as meeting playbooks
    #     """
    #     meeting_playbooks = []
    #     for playbook in playbooks.values():
    #         if playbook.meeting:
    #             meeting_playbooks.append(playbook.name)
    #     return meeting_playbooks

    # def is_meeting_playbook(
    #     self, playbook_name: str, playbooks: Dict[str, Playbook]
    # ) -> bool:
    #     """Check if a playbook is a meeting playbook.

    #     Args:
    #         playbook_name: Name of the playbook to check
    #         playbooks: Dictionary of available playbooks

    #     Returns:
    #         True if the playbook is a meeting playbook
    #     """
    #     playbook = playbooks.get(playbook_name)
    #     if not playbook:
    #         return False
    #     return playbook.meeting

    async def create_meeting(
        self, playbook: Playbook, kwargs: Dict[str, Any]
    ) -> Meeting:
        """Create meeting and prepare for invitations.

        Args:
            playbook: The playbook to create a meeting for
            kwargs: Keyword arguments passed to the playbook

        Returns:
            The created meeting
        """
        meeting_id = self.program.meeting_id_registry.generate_meeting_id()

        # Create meeting record
        meeting = Meeting(
            id=meeting_id,
            owner_id=self.agent_id,
            created_at=datetime.now(),
            topic=kwargs.get("topic", f"{playbook.name} meeting"),
        )

        debug(
            f"DEBUG create_meeting: Created meeting with id={meeting_id}, shared_state id={id(meeting.shared_state)}"
        )
        self.agent.owned_meetings[meeting_id] = meeting
        # Note: Meeting class requires BaseAgent object - playbook_executor is the agent
        meeting.agent_joined(self.playbook_executor)

        # Create asyncio.Event for tracking invitation responses
        meeting.invitation_event = asyncio.Event()

        # Figure out the attendees
        if "attendees" in kwargs and kwargs["attendees"]:
            # Either provided in the playbook call, e.g. attendees=["agent 1000", "agent 1001", "human"]
            meeting.required_attendees = (
                await self.program.get_agents_by_klasses_or_specs(kwargs["attendees"])
            )

            if not meeting.required_attendees:
                raise ValueError(
                    f"Unknown attendees {kwargs['attendees']} for meeting {meeting_id} with playbook {playbook.name}"
                )

        else:
            # Or configured in playbook metadata, e.g. required_attendees:["Accountant", "user"]
            if playbook.required_attendees or playbook.optional_attendees:
                try:
                    meeting.required_attendees = (
                        await self.program.get_agents_by_klasses(
                            playbook.required_attendees
                        )
                    )

                    meeting.optional_attendees = (
                        await self.program.get_agents_by_klasses(
                            playbook.optional_attendees
                        )
                    )
                except KlassNotFoundError:
                    raise ValueError(
                        f"Unknown required attendees {playbook.required_attendees} or optional attendees {playbook.optional_attendees} for meeting {meeting_id} with playbook {playbook.name}"
                    )

        if not meeting.required_attendees and not meeting.optional_attendees:
            raise ValueError(
                f"Unknown attendees for meeting {meeting_id} with playbook {playbook.name}"
            )

        # Ensure all attendee agents are running so they can process invitations
        for attendee in meeting.required_attendees + meeting.optional_attendees:
            if isinstance(attendee, HumanAgent):
                continue
            await self.program.runtime.start_agent(attendee)

        # Create meeting channel with all potential participants
        # Deduplicate by agent ID to avoid duplicate message delivery
        participant_list = (
            [self.playbook_executor]
            + meeting.required_attendees
            + meeting.optional_attendees
        )
        seen_ids = set()
        all_participants = []
        for participant in participant_list:
            if participant.id not in seen_ids:
                seen_ids.add(participant.id)
                all_participants.append(participant)

        await self.program.create_meeting_channel(meeting_id, all_participants)
        debug(
            f"Agent {self.agent_id}: Created meeting channel {meeting_id} with {len(all_participants)} participants"
        )

        # Kickoff broadcast: inform everyone the meeting started
        attendee_strs = []
        for p in all_participants:
            if isinstance(p, HumanAgent):
                attendee_strs.append("User(human)")
            else:
                attendee_strs.append(f"{p.klass}(agent {p.id})")
        kickoff = (
            f"Meeting {meeting_id} about {meeting.topic} started with {attendee_strs}"
        )
        await self.program.route_message(
            sender_id=self.agent_id,
            sender_klass=self.agent_klass,
            receiver_spec=str(MeetingID.parse(meeting_id)),
            message=kickoff,
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id=meeting_id,
        )
        # Also send to the owner (meeting broadcasts don't deliver to sender)
        await self.program.route_message(
            sender_id=self.agent_id,
            sender_klass=self.agent_klass,
            receiver_spec=str(AgentID.parse(self.agent_id)),
            message=kickoff,
            message_type=MessageType.DIRECT,
        )

        # Send invitations concurrently
        invitation_tasks = []

        # Create tasks for all required attendees
        for attendee in meeting.required_attendees:
            future = self._invite_to_meeting(meeting, attendee)
            if future:
                invitation_tasks.append(asyncio.create_task(future))

        # Create tasks for all optional attendees
        for attendee in meeting.optional_attendees:
            future = self._invite_to_meeting(meeting, attendee)
            if future:
                invitation_tasks.append(asyncio.create_task(future))

        # Yield for other tasks (async yield point)
        await asyncio.sleep(0)

        # Wait for all invitations to be sent
        if invitation_tasks:
            await asyncio.gather(*invitation_tasks)

        return meeting

    async def _invite_to_meeting(
        self, meeting: Meeting, target_agent: "BaseAgent"
    ) -> str:
        """Invite an agent to a meeting.

        Creates invitation record and sends invitation message. Human agents
        are automatically joined without invitation.

        Args:
            meeting: The meeting to invite to
            target_agent: The agent to invite

        Returns:
            Response message describing the invitation result
        """
        # Check if the target agent is already a participant
        if meeting.is_participant(target_agent.id):
            pass
        elif isinstance(target_agent, HumanAgent):
            meeting.agent_joined(target_agent)
        else:
            meeting.invitations[target_agent.id] = MeetingInvitation(
                agent=target_agent,
                created_at=datetime.now(),
                status=MeetingInvitationStatus.PENDING,
            )

            # For LocalAIAgents, store meeting reference for direct shared_state access
            debug(
                f"DEBUG _invite: target_agent={target_agent}, id={target_agent.id}, type={type(target_agent)}, is LocalAIAgent={isinstance(target_agent, LocalAIAgent)}"
            )

            if isinstance(target_agent, LocalAIAgent):
                if not hasattr(target_agent, "_pending_meeting_invitations"):
                    target_agent._pending_meeting_invitations = {}
                    debug(
                        f"DEBUG _invite: Created _pending_meeting_invitations for agent {target_agent.id}"
                    )
                meeting_id_obj = MeetingID.parse(meeting.id)
                target_agent._pending_meeting_invitations[meeting_id_obj.id] = meeting
                debug(
                    f"DEBUG _invite: Stored meeting {meeting.id} (parsed: {meeting_id_obj.id}) for agent {target_agent.id}, dict now has keys: {list(target_agent._pending_meeting_invitations.keys())}"
                )
                debug(
                    f"DEBUG _invite: shared_state id for meeting {meeting.id}: {id(meeting.shared_state)}"
                )
            else:
                debug(
                    f"DEBUG _invite: target_agent {target_agent.id} is NOT a LocalAIAgent!"
                )

            await self._send_invitation(meeting, target_agent)

        # Response is not currently surfaced; callers use a summary message.
        return f"Invited attendees to meeting {meeting.id}"

    async def _send_invitation(
        self, meeting: Meeting, target_agent: "BaseAgent"
    ) -> str:
        """Send meeting invitation to an agent using the message system.

        Routes a MEETING_INVITATION message to the target agent and logs it.

        Args:
            meeting: The meeting to send the invitation to
            target_agent: The agent to send the invitation to

        Returns:
            Response message confirming invitation was sent
        """

        # Send structured invitation message (as background task to avoid deadlock)
        # The invitation handler on receiving side will process synchronously and
        # send response as another background task, breaking the cycle.
        invitation_content = meeting.topic or "Meeting"

        self._create_background_task(
            self.program.route_message(
                sender_id=self.agent_id,
                sender_klass=self.agent_klass,
                receiver_spec=str(AgentID.parse(target_agent.id)),
                message=invitation_content,
                message_type=MessageType.MEETING_INVITATION,
                meeting_id=meeting.id,
            )
        )

        response = (
            f"Invited {str(target_agent)} to meeting {meeting.id}: {invitation_content}"
        )
        self.agent.session_log.append(response)
        meeting_msg = MeetingLLMMessage(response, meeting_id=meeting.id)
        self.agent.call_stack.add_llm_message(meeting_msg)

        return response

    async def InviteToMeeting(
        self, meeting_id: str, attendees: List[str]
    ) -> Optional[str]:
        """Invite agents to a meeting.

        Only the meeting owner can invite attendees. Sends invitations
        concurrently to all specified attendees.

        Args:
            meeting_id: The ID of the meeting to invite to
            attendees: List of agent specs to invite

        Returns:
            Error message if not owner, None if successful
        """
        if meeting_id not in self.agent.owned_meetings:
            return f"I am not the owner of meeting {meeting_id}, so cannot invite attendees"

        meeting = self.agent.owned_meetings[meeting_id]
        attendees = self.program.get_agents_by_specs(attendees)

        # Send invitations concurrently
        invitation_tasks = []
        for attendee in attendees:
            future = self._invite_to_meeting(meeting, attendee)
            if future:
                invitation_tasks.append(asyncio.create_task(future))

        # Wait for all invitations and collect responses
        if invitation_tasks:
            responses = await asyncio.gather(*invitation_tasks)
            return "\n".join(responses)
        return ""

    async def _wait_for_required_attendees(
        self, meeting: Meeting, timeout_seconds: int = 30
    ):
        """Wait for required attendees to join the meeting before proceeding.

        Args:
            meeting: The meeting to wait for
            timeout_seconds: Maximum time to wait for attendees

        Raises:
            TimeoutError: If required attendees don't join within timeout
            ValueError: If required attendee rejects the invitation
        """
        # If no attendees to wait for, proceed immediately
        if not meeting.required_attendees:
            message = f"No required attendees to wait for in meeting {meeting.id} - proceeding immediately"
            self.agent.session_log.append(message)
            meeting_msg = MeetingLLMMessage(message, meeting_id=meeting.id)
            self.agent.call_stack.add_llm_message(meeting_msg)
            return

        messages = f"Waiting for required attendees to join meeting {meeting.id}: {[attendee.__repr__() for attendee in meeting.required_attendees]}"
        self.agent.session_log.append(messages)
        meeting_msg = MeetingLLMMessage(messages, meeting_id=meeting.id)
        self.agent.call_stack.add_llm_message(meeting_msg)

        # Event-driven waiting: wait for invitation responses
        start_time = asyncio.get_event_loop().time()

        while meeting.has_pending_invitations():
            # Calculate remaining timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            remaining_timeout = timeout_seconds - elapsed

            if remaining_timeout <= 0:
                raise TimeoutError(
                    f"Timeout waiting for required attendees to join meeting {meeting.id}. "
                    f"Missing: {[attendee.__repr__() for attendee in meeting.missing_required_attendees()]}"
                )

            try:
                # Wait for invitation event (signaled when any response received)
                await asyncio.wait_for(
                    meeting.invitation_event.wait(), timeout=remaining_timeout
                )
                meeting.invitation_event.clear()  # Reset for next wait

                # If any required attendee rejected, fail fast
                required_ids = {a.id for a in meeting.required_attendees}
                rejected_required = [
                    inv.agent
                    for aid, inv in meeting.invitations.items()
                    if aid in required_ids
                    and inv.status == MeetingInvitationStatus.REJECTED
                ]
                if rejected_required:
                    raise ValueError(
                        f"Required attendee(s) rejected meeting {meeting.id}: {[a.__repr__() for a in rejected_required]}"
                    )

                # Check if all required attendees have joined
                if not meeting.has_pending_invitations():
                    break

                # Log progress
                message = f"Waiting for remaining attendees: {[attendee.__repr__() for attendee in meeting.missing_required_attendees()]}"
                self.agent.session_log.append(message)

            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"Timeout waiting for required attendees to join meeting {meeting.id}. "
                    f"Missing: {[attendee.__repr__() for attendee in meeting.missing_required_attendees()]}"
                )

        message = f"All required attendees have joined meeting {meeting.id}: {[attendee.__repr__() for attendee in meeting.joined_attendees]}"
        self.agent.session_log.append(message)
        meeting_msg = MeetingLLMMessage(message, meeting_id=meeting.id)
        self.agent.call_stack.add_llm_message(meeting_msg)

        # Finally, set the meeting ID as the current meeting ID in the call stack
        self.agent.call_stack.peek().meeting_id = meeting.id

    def get_current_meeting_from_call_stack(self) -> Optional[str]:
        """Get meeting ID from top meeting playbook in call stack.

        Args:
            call_stack: The agent's call stack

        Returns:
            Meeting ID if currently in a meeting, None otherwise
        """
        call_stack = self.agent.call_stack
        for frame in reversed(call_stack.frames):
            if frame.is_meeting and frame.meeting_id:
                return frame.meeting_id
        return None

    async def _add_message_to_buffer(self, message: Message) -> bool:
        """Add a message to buffer and notify waiting processes.

        This is the single entry point for all incoming messages.
        Handles meeting invitations and responses immediately.
        Meeting broadcasts are batched with a rolling timeout to minimize thrashing.

        Args:
            message: Message to add to buffer

        Returns:
            True if message was handled, False otherwise
        """
        debug(
            f"Agent {self.agent_id}: _add_message_to_buffer: type={message.message_type}, from={message.sender_id}, preview={message.content[:60]}..."
        )

        if message.message_type == MessageType.MEETING_INVITATION:
            # Process meeting invitation immediately
            debug(f"Agent {self.agent_id}: Processing MEETING_INVITATION immediately")
            return await self._handle_meeting_invitation_immediately(message)
        elif message.message_type == MessageType.MEETING_INVITATION_RESPONSE:
            # Process meeting response immediately and signal event
            debug(
                f"Agent {self.agent_id}: Processing MEETING_INVITATION_RESPONSE immediately"
            )
            await self._handle_meeting_response_immediately(message)

            # Signal the meeting's invitation event to wake up _wait_for_required_attendees
            meeting_id_obj = message.meeting_id
            if (
                meeting_id_obj
                and hasattr(self.agent, "owned_meetings")
                and meeting_id_obj.id in self.agent.owned_meetings
            ):
                meeting = self.agent.owned_meetings[meeting_id_obj.id]
                if hasattr(meeting, "invitation_event"):
                    meeting.invitation_event.set()
                    debug(
                        f"Agent {self.agent_id}: Signaled invitation event for meeting {meeting_id_obj.id}"
                    )

            return True
        elif message.message_type == MessageType.MEETING_BROADCAST:
            # Treat system kickoff banners as informational only: add to session log
            # and keep them out of the message queue so ProcessMessages doesn't try
            # to "join" a meeting based on them.
            if (
                message.content.startswith("Meeting ")
                and " started with " in message.content
            ):
                debug(f"Agent {self.agent_id}: Processing meeting kickoff banner")
                self.agent.session_log.append(message.content)
                meeting_id = message.meeting_id.id if message.meeting_id else None
                meeting_msg = MeetingLLMMessage(message.content, meeting_id=meeting_id)
                self.agent.call_stack.add_llm_message(meeting_msg)
                return True

            # Batch other meeting broadcasts with rolling timeout to minimize thrashing
            debug(
                f"Agent {self.agent_id}: Adding meeting broadcast to collector (will wait up to {self.message_collector.timeout_seconds}s)"
            )
            await self.message_collector.add_message(message)
            return True
        return False

    async def _deliver_collected_messages(self, messages: List[Message]) -> None:
        """Deliver batched messages to the agent's message queue.

        This is called by RollingMessageCollector when the timeout expires.

        Args:
            messages: List of messages to deliver
        """
        debug(
            f"Agent {self.agent_id}: _deliver_collected_messages: Delivering {len(messages)} batched messages to queue"
        )
        # Add all messages to the agent's message queue
        for i, message in enumerate(messages):
            debug(
                f"Agent {self.agent_id}: Queuing message {i+1}/{len(messages)} from {message.sender_id}: {message.content[:60]}..."
            )
            await self.agent._message_queue.put(message)
        debug(
            f"Agent {self.agent_id}: All {len(messages)} messages queued successfully"
        )

    async def flush_pending_messages(self, meeting_id: Optional[str] = None) -> None:
        """Force immediate delivery of buffered messages from RollingMessageCollector.

        Called before prompt construction to ensure all agent communications
        are included in the LLM context.

        Args:
            meeting_id: Optional meeting ID (currently unused, reserved for future filtering)
        """
        if self.message_collector:
            buffer_size = len(self.message_collector.buffer)
            if buffer_size > 0:
                debug(
                    f"Agent {self.agent_id}: flush_pending_messages: Flushing {buffer_size} buffered messages"
                )
            await self.message_collector.flush()

    async def _handle_meeting_invitation_immediately(self, message) -> None:
        """Handle meeting invitation immediately without buffering."""
        debug(
            f"DEBUG _handle_meeting_invitation_immediately: CALLED for agent {self.agent_id}, message from {message.sender_id}"
        )
        # Extract meeting information from the message
        meeting_id_obj = getattr(message, "meeting_id", None)
        sender_id = message.sender_id.id
        topic = message.content  # The invitation content contains the topic

        meeting_id = meeting_id_obj.id if meeting_id_obj else None

        if meeting_id:
            # Use async task to handle the invitation since this is called synchronously
            return await self._process_meeting_invitation(sender_id, meeting_id, topic)
        else:
            log = f"Received meeting invitation from {sender_id} without meeting_id"
            self.agent.session_log.append(log)
            session_msg = SessionLogLLMMessage(log, log_level="warning")
            self.agent.call_stack.add_llm_message(session_msg)
            return True

    async def _handle_meeting_response_immediately(self, message) -> None:
        """Handle meeting response immediately without buffering."""
        # Process the meeting response using the handler that updates meeting state
        await self.meeting_message_handler.handle_meeting_response(
            message, self.playbook_executor
        )

    async def _process_meeting_invitation(
        self, inviter_id: str, meeting_id: str, topic: str
    ):
        """Process a meeting invitation by checking for suitable meeting playbooks.

        Args:
            inviter_id: ID of the agent that sent the invitation
            meeting_id: ID of the meeting
            topic: Topic/description of the meeting
        """
        debug(
            f"DEBUG _process_meeting_invitation: CALLED for agent {self.agent_id}, meeting {meeting_id}"
        )
        log = f"Received meeting invitation for meeting {meeting_id} from {inviter_id} for '{topic}'"
        self.agent.session_log.append(log)
        meeting_msg = MeetingLLMMessage(log, meeting_id=meeting_id)
        self.agent.call_stack.add_llm_message(meeting_msg)

        # Check if agent is busy (has active call stack)
        from playbooks.program import is_agent_busy

        if is_agent_busy(self.agent):
            log = f"Rejecting meeting {meeting_id} - agent is busy"
            self.agent.session_log.append(log)
            meeting_msg = MeetingLLMMessage(log, meeting_id=meeting_id)
            self.agent.call_stack.add_llm_message(meeting_msg)
            if self.program:
                # Send rejection as background task to avoid reentrancy deadlock
                self._create_background_task(
                    self.program.route_message(
                        sender_id=self.agent_id,
                        sender_klass=self.agent_klass,
                        receiver_spec=str(AgentID.parse(inviter_id)),
                        message=f"REJECTED {meeting_id}",
                        message_type=MessageType.MEETING_INVITATION_RESPONSE,
                        meeting_id=meeting_id,
                    )
                )
            return True

        # Deterministic meeting handling: accept + run the (single) meeting playbook.
        meeting_playbooks = [
            pb.name
            for pb in self.playbook_executor.playbooks.values()
            if getattr(pb, "meeting", False)
        ]
        if len(meeting_playbooks) != 1:
            if self.program:
                # Send rejection as background task to avoid reentrancy deadlock
                self._create_background_task(
                    self.program.route_message(
                        sender_id=self.agent_id,
                        sender_klass=self.agent_klass,
                        receiver_spec=str(AgentID.parse(inviter_id)),
                        message=f"REJECTED {meeting_id}",
                        message_type=MessageType.MEETING_INVITATION_RESPONSE,
                        meeting_id=meeting_id,
                    )
                )
            return True

        playbook_name = meeting_playbooks[0]
        await self._accept_meeting_invitation(
            meeting_id=meeting_id,
            inviter_id=inviter_id,
            topic=topic,
            playbook_name=playbook_name,
        )
        await self._execute_meeting_playbook(
            meeting_id=MeetingID.parse(meeting_id).id, playbook_name=playbook_name
        )
        return True

    async def _accept_meeting_invitation(
        self, meeting_id: str, inviter_id: str, topic: str, playbook_name: str
    ) -> bool:
        # Accept the invitation and join the meeting
        debug(
            f"DEBUG _accept_meeting_invitation: CALLED for agent {self.agent_id}, meeting {meeting_id}"
        )
        debug(f"Agent {self.agent_id}: Accepting meeting invitation {meeting_id}")
        log = f"Accepting meeting invitation {meeting_id}"
        meeting_id_obj = MeetingID.parse(meeting_id)
        debug(
            f"DEBUG _accept: Original meeting_id={meeting_id}, parsed meeting_id={meeting_id_obj.id}"
        )
        meeting_id = meeting_id_obj.id
        self.agent.session_log.append(log)
        meeting_msg = MeetingLLMMessage(log, meeting_id=meeting_id)
        self.agent.call_stack.add_llm_message(meeting_msg)

        # Store meeting info in joined_meetings for future message routing
        # Get meeting reference if available (LocalAIAgent)
        shared_state_ref = None
        debug(
            f"DEBUG _accept: agent={self.agent_id}, type={type(self.agent)}, has _pending={hasattr(self.agent, '_pending_meeting_invitations')}"
        )

        if hasattr(self.agent, "_pending_meeting_invitations"):
            debug(
                f"DEBUG _accept: _pending keys before pop: {list(self.agent._pending_meeting_invitations.keys())}"
            )
            pending_meeting = self.agent._pending_meeting_invitations.pop(
                meeting_id, None
            )
            debug(
                f"DEBUG _accept: popped meeting for {meeting_id}: {pending_meeting is not None}"
            )
            if pending_meeting:
                shared_state_ref = pending_meeting.shared_state
                debug(
                    f"DEBUG _accept: Got shared_state ref: {id(shared_state_ref)}, type={type(shared_state_ref)}, empty={len(shared_state_ref) == 0}"
                )
            else:
                debug(f"DEBUG _accept: No pending_meeting found for {meeting_id}")
        else:
            debug(
                f"DEBUG _accept: Agent {self.agent_id} doesn't have _pending_meeting_invitations attribute"
            )

        if shared_state_ref is None:
            # Look up the shared state from the meeting owner's owned_meetings
            inviter_agent = self.program.agents_by_id.get(inviter_id)
            if (
                inviter_agent
                and hasattr(inviter_agent, "owned_meetings")
                and meeting_id in inviter_agent.owned_meetings
            ):
                meeting_obj = inviter_agent.owned_meetings[meeting_id]
                shared_state_ref = meeting_obj.shared_state
                debug(
                    f"DEBUG _accept: Got shared_state from inviter's meeting: {id(shared_state_ref)}"
                )
            else:
                debug(
                    f"DEBUG _accept: Could not find meeting {meeting_id} in inviter {inviter_id}'s owned_meetings, creating fallback"
                )
                # Create a new shared state as fallback (though this won't be shared with other participants)
                from box import Box

                shared_state_ref = Box(default_box=True)

        self.agent.joined_meetings[meeting_id] = JoinedMeeting(
            id=meeting_id,
            owner_id=inviter_id,
            topic=topic,
            joined_at=datetime.now(),
            shared_state=shared_state_ref,
        )
        debug(f"Agent {self.agent_id}: joined_meetings {self.agent.joined_meetings}")

        # Send structured JOINED response as background task to avoid reentrancy deadlock
        # (we're currently inside a message delivery path; awaiting route_message would deadlock)
        if self.program:
            self._create_background_task(
                self.program.route_message(
                    sender_id=self.agent_id,
                    sender_klass=self.agent_klass,
                    receiver_spec=str(AgentID.parse(inviter_id)),
                    message=f"JOINED {meeting_id}",
                    message_type=MessageType.MEETING_INVITATION_RESPONSE,
                    meeting_id=meeting_id,
                )
            )

        # The initiator will add us as a participant when they receive our JOINED message
        # We don't directly access the meeting object here to support remote agents

    async def _execute_meeting_playbook(
        self, meeting_id: str, playbook_name: str
    ) -> None:
        try:
            meeting_playbook = self.playbook_executor.playbooks[playbook_name]

            meeting = self.agent.joined_meetings[meeting_id]
            topic = meeting.topic

            log = f"Starting meeting playbook '{meeting_playbook.name}' for meeting {meeting_id}"
            debug(f"Agent {self.agent_id}: {log}")
            self.agent.session_log.append(log)
            meeting_msg = MeetingLLMMessage(log, meeting_id=meeting_id)
            self.agent.call_stack.add_llm_message(meeting_msg)

            # Execute the meeting playbook with meeting context
            debug(
                "Agent executing meeting playbook",
                agent_id=self.agent_id,
                playbook_name=meeting_playbook.name,
            )

            async def execute_with_agent_context():
                """Execute meeting playbook."""
                await self.playbook_executor.execute_playbook(
                    meeting_playbook.name,
                    args=[],
                    kwargs={"meeting_id": meeting_id, "topic": topic},
                )

            task = asyncio.create_task(execute_with_agent_context())
            task.add_done_callback(
                lambda t: debug(
                    "Meeting playbook task done",
                    agent_id=self.agent_id,
                    playbook_name=meeting_playbook.name,
                )
            )
            await asyncio.gather(task)

        except Exception as e:
            log = f"Error executing meeting playbook for {meeting_id}: {str(e)}"
            self.agent.session_log.append(log)
            meeting_msg = MeetingLLMMessage(log, meeting_id=meeting_id)
            self.agent.call_stack.add_llm_message(meeting_msg)
            # Send error message to meeting
            if self.program:
                await self.program.route_message(
                    sender_id=self.agent_id,
                    sender_klass=self.agent_klass,
                    receiver_spec=str(AgentID.parse(meeting.owner_id)),
                    message=f"Meeting {meeting_id}: Error in playbook execution - {str(e)}",
                    message_type=MessageType.MEETING_INVITATION_RESPONSE,
                    meeting_id=meeting_id,
                )

    # async def initialize_meeting_playbook(
    #     self,
    #     playbook_name: str,
    #     kwargs: Dict[str, Any],
    #     playbooks: Dict[str, Any],
    #     meeting_registry: MeetingRegistry,
    #     session_log,
    #     wait_for_attendees_callback,
    # ):
    #     """Initialize meeting before executing meeting playbook.

    #     This method is called implicitly before any meeting playbook executes.
    #     For new meetings, it creates the meeting, sends invitations, and waits for required participants.
    #     For existing meetings (when meeting_id is provided), it joins the existing meeting.

    #     Args:
    #         playbook_name: Name of the meeting playbook being executed
    #         kwargs: Keyword arguments passed to the playbook
    #         playbooks: Dictionary of available playbooks
    #         meeting_registry: Registry for meeting IDs
    #         session_log: Session log for recording events
    #         wait_for_attendees_callback: Callback to wait for required attendees
    #     """
    #     # Check if we're joining an existing meeting (meeting_id provided) or creating a new one
    #     existing_meeting_id = kwargs.get("meeting_id")

    #     if existing_meeting_id:
    #         # Joining an existing meeting - just proceed with execution
    #         session_log.append(
    #             f"Joining existing meeting {existing_meeting_id} for playbook {playbook_name}"
    #         )
    #         return  # No need to create meeting or wait for attendees

    #     # Creating a new meeting
    #     kwargs_attendees = kwargs.get("attendees", [])
    #     topic = kwargs.get("topic", f"{playbook_name} meeting")

    #     # Determine attendee strategy: kwargs attendees take precedence
    #     if kwargs_attendees:
    #         # If attendees specified in kwargs, treat them as required
    #         required_attendees = kwargs_attendees
    #         all_attendees = kwargs_attendees
    #         session_log.append(
    #             f"Using kwargs attendees as required for meeting {playbook_name}: {required_attendees}"
    #         )
    #     else:
    #         # If no kwargs attendees, use metadata-defined attendees
    #         metadata_required, metadata_optional = self.get_playbook_attendees(
    #             playbook_name, playbooks
    #         )
    #         required_attendees = metadata_required
    #         all_attendees = list(set(metadata_required + metadata_optional))
    #         session_log.append(
    #             f"Using metadata attendees for meeting {playbook_name}: required={metadata_required}, optional={metadata_optional}"
    #         )

    #     # Filter out the requester from required attendees (they're already present)
    #     required_attendees_to_wait_for = [
    #         attendee
    #         for attendee in required_attendees
    #         if attendee != self.agent_klass and attendee != self.agent_id
    #     ]

    #     # Create the meeting
    #     meeting_id = await self.create_meeting(
    #         invited_agents=all_attendees, topic=topic, meeting_registry=meeting_registry
    #     )

    #     # Store meeting_id in kwargs for the playbook to access
    #     kwargs["meeting_id"] = meeting_id

    #     # Log the meeting initialization
    #     session_log.append(
    #         f"Initialized meeting {meeting_id} for playbook {playbook_name}"
    #     )

    #     # Wait for required attendees to join before proceeding
    #     await wait_for_attendees_callback(meeting_id, required_attendees_to_wait_for)
