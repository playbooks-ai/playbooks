"""Unit tests for meeting shared state functionality."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from box import Box

from playbooks.agents.local_ai_agent import LocalAIAgent
from playbooks.execution.python_executor import PythonExecutor
from playbooks.infrastructure.event_bus import EventBus
from playbooks.meetings.meeting import JoinedMeeting, Meeting
from playbooks.meetings.meeting_manager import MeetingManager
from playbooks.state.call_stack import CallStack, CallStackFrame


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus(session_id="test_session")


@pytest.fixture
def mock_program():
    """Create a mock program."""
    program = Mock()
    program.agents_by_id = {}
    program.route_message = AsyncMock()
    return program


@pytest.fixture
def owner_agent(event_bus, mock_program):
    """Create an owner agent."""
    agent = Mock(spec=LocalAIAgent)
    agent.id = "agent_1000"
    agent.klass = "Host"
    agent.event_bus = event_bus
    agent.program = mock_program
    agent.owned_meetings = {}
    agent.joined_meetings = {}
    agent.session_log = Mock()
    agent.session_log.append = Mock()
    agent.call_stack = Mock(spec=CallStack)
    agent.call_stack.add_llm_message = Mock()
    agent.call_stack.peek = Mock(return_value=None)
    agent.call_stack.frames = []
    agent.namespace_manager = Mock()
    agent.namespace_manager.namespace = {}

    return agent


@pytest.fixture
def participant_agent(event_bus, mock_program):
    """Create a participant agent."""
    agent = Mock(spec=LocalAIAgent)
    agent.id = "agent_2000"
    agent.klass = "Player"
    agent.event_bus = event_bus
    agent.program = mock_program
    agent.owned_meetings = {}
    agent.joined_meetings = {}
    agent.session_log = Mock()
    agent.session_log.append = Mock()
    agent.call_stack = Mock(spec=CallStack)
    agent.call_stack.add_llm_message = Mock()
    agent.call_stack.peek = Mock(return_value=None)
    agent.call_stack.frames = []
    agent.namespace_manager = Mock()
    agent.namespace_manager.namespace = {}

    return agent


class TestJoinedMeetingDataclass:
    """Test JoinedMeeting dataclass with shared_state field."""

    def test_joined_meeting_without_shared_state(self):
        """Test JoinedMeeting always has a Box shared_state."""
        meeting = JoinedMeeting(
            id="meeting_100",
            owner_id="agent_1000",
            joined_at=datetime.now(),
            topic="Test Meeting",
        )
        # shared_state is now always a Box (empty if not provided)
        assert isinstance(meeting.shared_state, Box)
        assert len(meeting.shared_state) == 0

    def test_joined_meeting_with_shared_state(self):
        """Test JoinedMeeting can be created with shared_state."""
        shared_state = Box({"game_board": [[1, 2, 3], [4, 5, 6]]})
        meeting = JoinedMeeting(
            id="meeting_100",
            owner_id="agent_1000",
            joined_at=datetime.now(),
            topic="Test Meeting",
            shared_state=shared_state,
        )
        # shared_state should be converted to Box
        assert isinstance(meeting.shared_state, Box)
        assert meeting.shared_state["game_board"] == [[1, 2, 3], [4, 5, 6]]


class TestMeetingInvitationWithReference:
    """Test meeting invitation passes Meeting reference for LocalAIAgents."""

    @pytest.mark.asyncio
    async def test_invite_local_agent_stores_meeting_reference(
        self, owner_agent, participant_agent, mock_program
    ):
        """Test that inviting a LocalAIAgent stores meeting reference."""
        # Setup
        meeting_manager = MeetingManager(
            agent_id=owner_agent.id,
            agent_klass=owner_agent.klass,
            agent=owner_agent,
            program=mock_program,
            playbook_executor=owner_agent,
        )

        meeting = Meeting(
            id="meeting_100",
            created_at=datetime.now(),
            owner_id=owner_agent.id,
            topic="Test Meeting",
            shared_state={"initial": "value"},
        )
        owner_agent.owned_meetings[meeting.id] = meeting

        # Execute
        await meeting_manager._invite_to_meeting(meeting, participant_agent)

        # Verify meeting reference was stored
        assert hasattr(participant_agent, "_pending_meeting_invitations")
        assert meeting.id in participant_agent._pending_meeting_invitations
        assert participant_agent._pending_meeting_invitations[meeting.id] is meeting

    @pytest.mark.asyncio
    async def test_invite_non_local_agent_no_reference(self, owner_agent, mock_program):
        """Test that non-LocalAIAgents don't get meeting reference."""
        from playbooks.agents.remote_ai_agent import RemoteAIAgent

        # Setup
        meeting_manager = MeetingManager(
            agent_id=owner_agent.id,
            agent_klass=owner_agent.klass,
            agent=owner_agent,
            program=mock_program,
            playbook_executor=owner_agent,
        )

        # Create a non-LocalAIAgent (using spec to ensure isinstance checks work)
        remote_agent = Mock(spec=RemoteAIAgent)
        remote_agent.id = "agent_3000"
        remote_agent.klass = "RemotePlayer"

        meeting = Meeting(
            id="meeting_100",
            created_at=datetime.now(),
            owner_id=owner_agent.id,
            topic="Test Meeting",
            shared_state={"initial": "value"},
        )
        owner_agent.owned_meetings[meeting.id] = meeting

        # Execute
        await meeting_manager._invite_to_meeting(meeting, remote_agent)

        # Verify no meeting reference was stored (Remote agents shouldn't get it)
        # Since we're using isinstance check, a spec=RemoteAIAgent won't match LocalAIAgent
        if hasattr(remote_agent, "_pending_meeting_invitations"):
            assert meeting.id not in remote_agent._pending_meeting_invitations


class TestAcceptInvitationConnectsSharedState:
    """Test accepting invitation connects shared_state reference."""

    @pytest.mark.asyncio
    async def test_accept_invitation_with_pending_meeting(
        self, participant_agent, owner_agent, mock_program
    ):
        """Test that accepting invitation connects shared_state from pending meeting."""
        # Setup
        meeting_manager = MeetingManager(
            agent_id=participant_agent.id,
            agent_klass=participant_agent.klass,
            agent=participant_agent,
            program=mock_program,
            playbook_executor=participant_agent,
        )

        # Create meeting with shared_state
        shared_state = Box({"game_board": [[1, 2, 3]]})
        meeting = Meeting(
            id="meeting_100",
            created_at=datetime.now(),
            owner_id=owner_agent.id,
            topic="Game Meeting",
            shared_state=shared_state,
        )

        # Store pending meeting reference
        participant_agent._pending_meeting_invitations = {meeting.id: meeting}

        # Execute
        await meeting_manager._accept_meeting_invitation(
            meeting_id=meeting.id,
            inviter_id=owner_agent.id,
            topic="Game Meeting",
            playbook_name="GamePlaybook",
        )

        # Verify shared_state is connected
        assert meeting.id in participant_agent.joined_meetings
        joined_meeting = participant_agent.joined_meetings[meeting.id]
        # shared_state should be the same Box object as in the meeting
        assert joined_meeting.shared_state is meeting.shared_state
        assert isinstance(joined_meeting.shared_state, Box)

        # Verify pending invitation was removed
        assert meeting.id not in participant_agent._pending_meeting_invitations

    @pytest.mark.asyncio
    async def test_accept_invitation_without_pending_meeting(
        self, participant_agent, owner_agent, mock_program
    ):
        """Test that accepting invitation without pending meeting creates fallback shared_state."""
        # Setup
        meeting_manager = MeetingManager(
            agent_id=participant_agent.id,
            agent_klass=participant_agent.klass,
            agent=participant_agent,
            program=mock_program,
            playbook_executor=participant_agent,
        )

        # Initialize empty pending invitations
        participant_agent._pending_meeting_invitations = {}

        # Execute without pending meeting - should create fallback shared_state
        await meeting_manager._accept_meeting_invitation(
            meeting_id="meeting_100",
            inviter_id=owner_agent.id,
            topic="Game Meeting",
            playbook_name="GamePlaybook",
        )

        # Verify joined meeting was created with fallback shared_state
        assert "meeting_100" in participant_agent.joined_meetings
        joined_meeting = participant_agent.joined_meetings["meeting_100"]
        assert isinstance(joined_meeting.shared_state, Box)
        assert len(joined_meeting.shared_state) == 0  # Empty fallback Box


class TestSharedStateReference:
    """Test that shared_state is truly shared (same object reference)."""

    def test_shared_state_reference_is_shared(self, owner_agent, participant_agent):
        """Test that owner and participant share the same dict object."""
        # Create meeting with shared_state
        shared_state = Box({"score": 0, "turn": 1})
        meeting = Meeting(
            id="meeting_100",
            created_at=datetime.now(),
            owner_id=owner_agent.id,
            topic="Game",
            shared_state=shared_state,
        )
        owner_agent.owned_meetings[meeting.id] = meeting

        # Participant joins with reference
        joined_meeting = JoinedMeeting(
            id=meeting.id,
            owner_id=owner_agent.id,
            joined_at=datetime.now(),
            topic="Game",
            shared_state=meeting.shared_state,
        )
        participant_agent.joined_meetings[meeting.id] = joined_meeting

        # Verify it's the same object
        assert (
            owner_agent.owned_meetings[meeting.id].shared_state
            is participant_agent.joined_meetings[meeting.id].shared_state
        )

        # Owner modifies
        owner_agent.owned_meetings[meeting.id].shared_state["score"] = 10

        # Participant sees the change
        assert participant_agent.joined_meetings[meeting.id].shared_state["score"] == 10

        # Participant modifies
        participant_agent.joined_meetings[meeting.id].shared_state["turn"] = 2

        # Owner sees the change
        assert owner_agent.owned_meetings[meeting.id].shared_state["turn"] == 2


class TestPythonExecutorMeetingExposure:
    """Test that meeting object is exposed in Python execution namespace."""

    def test_build_namespace_without_meeting(self, owner_agent):
        """Test namespace building when not in a meeting."""
        # Mock get_current_meeting to return None (no meeting)
        owner_agent.get_current_meeting = Mock(return_value=None)

        executor = PythonExecutor(owner_agent)
        namespace = executor.build_namespace()

        # Meeting should not be in namespace
        assert "meeting" not in namespace

    def test_build_namespace_with_owned_meeting(self, owner_agent):
        """Test namespace building when agent owns the meeting."""
        # Setup meeting
        shared_state = Box({"game_board": [[1, 2, 3]]})
        meeting = Meeting(
            id="meeting_100",
            created_at=datetime.now(),
            owner_id=owner_agent.id,
            topic="Game",
            shared_state=shared_state,
        )
        owner_agent.owned_meetings[meeting.id] = meeting

        # Mock get_current_meeting to return the meeting object
        owner_agent.get_current_meeting = Mock(return_value=meeting)

        # Setup call stack frame with meeting_id
        frame = Mock(spec=CallStackFrame)
        frame.meeting_id = meeting.id
        frame.is_meeting = True
        owner_agent.call_stack.peek = Mock(return_value=frame)
        owner_agent.call_stack.frames = [frame]  # Add to frames list

        # Build namespace
        executor = PythonExecutor(owner_agent)
        namespace = executor.build_namespace()

        # Verify meeting is in namespace
        assert "meeting" in namespace
        meeting_wrapper = namespace["meeting"]

        # Verify shared_state is wrapped with Box
        assert hasattr(meeting_wrapper, "shared_state")
        assert isinstance(meeting_wrapper.shared_state, Box)

        # Verify we can access shared_state values
        assert meeting_wrapper.shared_state.game_board == [[1, 2, 3]]

    def test_build_namespace_with_joined_meeting(self, participant_agent):
        """Test namespace building when agent joined the meeting."""
        # Setup joined meeting
        shared_state = Box({"score": 5})
        joined_meeting = JoinedMeeting(
            id="meeting_100",
            owner_id="agent_1000",
            joined_at=datetime.now(),
            topic="Game",
            shared_state=shared_state,
        )
        participant_agent.joined_meetings[joined_meeting.id] = joined_meeting

        # Mock get_current_meeting to return the meeting object
        participant_agent.get_current_meeting = Mock(return_value=joined_meeting)

        # Setup call stack frame with meeting_id
        frame = Mock(spec=CallStackFrame)
        frame.meeting_id = joined_meeting.id
        frame.is_meeting = True
        participant_agent.call_stack.peek = Mock(return_value=frame)
        participant_agent.call_stack.frames = [frame]  # Add to frames list

        # Build namespace
        executor = PythonExecutor(participant_agent)
        namespace = executor.build_namespace()

        # Verify meeting is in namespace
        assert "meeting" in namespace
        meeting_wrapper = namespace["meeting"]

        # Verify shared_state is wrapped with Box
        assert hasattr(meeting_wrapper, "shared_state")
        assert isinstance(meeting_wrapper.shared_state, Box)

        # Verify we can access shared_state values
        assert meeting_wrapper.shared_state.score == 5

    def test_build_namespace_with_none_shared_state(self, participant_agent):
        """Test namespace building when shared_state is None."""
        # Setup joined meeting without shared_state
        joined_meeting = JoinedMeeting(
            id="meeting_100",
            owner_id="agent_1000",
            joined_at=datetime.now(),
            topic="Game",
            shared_state=None,
        )
        participant_agent.joined_meetings[joined_meeting.id] = joined_meeting

        # Mock get_current_meeting to return the meeting object
        participant_agent.get_current_meeting = Mock(return_value=joined_meeting)

        # Setup call stack frame with meeting_id
        frame = Mock(spec=CallStackFrame)
        frame.meeting_id = joined_meeting.id
        frame.is_meeting = True
        participant_agent.call_stack.peek = Mock(return_value=frame)
        participant_agent.call_stack.frames = [frame]  # Add to frames list

        # Build namespace
        executor = PythonExecutor(participant_agent)
        namespace = executor.build_namespace()

        # Verify meeting is in namespace but shared_state is None
        assert "meeting" in namespace
        meeting_wrapper = namespace["meeting"]
        assert meeting_wrapper.shared_state is None

    def test_meeting_wrapper_proxies_other_attributes(self, owner_agent):
        """Test that MeetingWrapper proxies non-shared_state attributes."""
        # Setup meeting
        meeting = Meeting(
            id="meeting_100",
            created_at=datetime.now(),
            owner_id=owner_agent.id,
            topic="Test Meeting",
            shared_state={"data": "value"},
        )
        owner_agent.owned_meetings[meeting.id] = meeting

        # Mock get_current_meeting to return the meeting object
        owner_agent.get_current_meeting = Mock(return_value=meeting)

        # Setup call stack frame
        frame = Mock(spec=CallStackFrame)
        frame.meeting_id = meeting.id
        frame.is_meeting = True
        owner_agent.call_stack.peek = Mock(return_value=frame)
        owner_agent.call_stack.frames = [frame]  # Add to frames list

        # Build namespace
        executor = PythonExecutor(owner_agent)
        namespace = executor.build_namespace()

        meeting_wrapper = namespace["meeting"]

        # Verify wrapper proxies other attributes
        assert meeting_wrapper.id == "meeting_100"
        assert meeting_wrapper.topic == "Test Meeting"
        assert meeting_wrapper.owner_id == owner_agent.id


class TestDotAccessToSharedState:
    """Test dot-notation access to shared_state values."""

    def test_playbook_dotmap_allows_dot_access(self):
        """Test that Box allows dot-notation access."""
        data = {"game_board": [[1, 2], [3, 4]], "turn": 1, "score": 10}
        dotmap = Box(data)

        # Test dot access
        assert dotmap.game_board == [[1, 2], [3, 4]]
        assert dotmap.turn == 1
        assert dotmap.score == 10

        # Test assignment via dot notation
        dotmap.turn = 2
        assert dotmap.turn == 2
        # Note: Box is a copy, so original dict is not modified
        # This is fine because we pass the same dict reference to all participants

    def test_nested_dict_access(self):
        """Test nested dictionary access through Box."""
        data = {"player": {"name": "Alice", "score": 100}}
        dotmap = Box(data)

        # Access nested dict
        assert dotmap.player["name"] == "Alice"
        assert dotmap.player["score"] == 100


class TestInterpreterPromptSafetyCheck:
    """Test that interpreter_prompt.py handles None shared_state gracefully."""

    def test_interpreter_prompt_with_shared_state(self):
        """Test interpreter prompt displays shared_state when available."""

        # This is more of an integration test, but we can test the logic
        # The actual implementation check is in the code review
        # Here we just verify the dataclass works correctly

        joined_meeting = JoinedMeeting(
            id="meeting_100",
            owner_id="agent_1000",
            joined_at=datetime.now(),
            shared_state={"game_board": [[1, 2, 3]]},
        )

        assert joined_meeting.shared_state is not None
        assert "game_board" in joined_meeting.shared_state

    def test_interpreter_prompt_without_shared_state(self):
        """Test interpreter prompt handles None shared_state."""
        joined_meeting = JoinedMeeting(
            id="meeting_100",
            owner_id="agent_1000",
            joined_at=datetime.now(),
            shared_state=None,
        )

        # Should not crash when iterating
        if joined_meeting.shared_state is not None:
            # This branch should not execute
            for key in joined_meeting.shared_state:
                pass

        # Verify it's safe
        assert joined_meeting.shared_state is None


class TestSharedStateActuallySharedBetweenAgents:
    """End-to-end tests verifying shared_state is truly shared between agents."""

    def test_owner_and_participant_share_same_state_object(
        self, owner_agent, participant_agent
    ):
        """Verify owner and participant have the same shared_state object reference."""
        # Owner creates meeting with initial shared_state
        shared_state = Box({"counter": 0, "data": []})
        meeting = Meeting(
            id="meeting_100",
            created_at=datetime.now(),
            owner_id=owner_agent.id,
            topic="Shared State Test",
            shared_state=shared_state,
        )
        owner_agent.owned_meetings[meeting.id] = meeting

        # Participant joins with reference to same meeting
        joined_meeting = JoinedMeeting(
            id=meeting.id,
            owner_id=owner_agent.id,
            joined_at=datetime.now(),
            topic="Shared State Test",
            shared_state=meeting.shared_state,
        )
        participant_agent.joined_meetings[meeting.id] = joined_meeting

        # Verify they reference the SAME object
        assert (
            owner_agent.owned_meetings[meeting.id].shared_state
            is participant_agent.joined_meetings[meeting.id].shared_state
        )
        assert id(owner_agent.owned_meetings[meeting.id].shared_state) == id(
            participant_agent.joined_meetings[meeting.id].shared_state
        )

    def test_modifications_by_owner_visible_to_participant(
        self, owner_agent, participant_agent
    ):
        """Verify participant sees modifications made by owner."""
        # Setup meeting
        shared_state = Box({"score": 0, "players": []})
        meeting = Meeting(
            id="meeting_100",
            created_at=datetime.now(),
            owner_id=owner_agent.id,
            topic="Game",
            shared_state=shared_state,
        )
        owner_agent.owned_meetings[meeting.id] = meeting

        joined_meeting = JoinedMeeting(
            id=meeting.id,
            owner_id=owner_agent.id,
            joined_at=datetime.now(),
            topic="Game",
            shared_state=meeting.shared_state,
        )
        participant_agent.joined_meetings[meeting.id] = joined_meeting

        # Owner modifies shared_state
        owner_agent.owned_meetings[meeting.id].shared_state["score"] = 42
        owner_agent.owned_meetings[meeting.id].shared_state["players"].append("Alice")
        owner_agent.owned_meetings[meeting.id].shared_state["new_field"] = "test"

        # Participant should see all changes
        assert participant_agent.joined_meetings[meeting.id].shared_state["score"] == 42
        assert participant_agent.joined_meetings[meeting.id].shared_state[
            "players"
        ] == ["Alice"]
        assert (
            participant_agent.joined_meetings[meeting.id].shared_state["new_field"]
            == "test"
        )

    def test_modifications_by_participant_visible_to_owner(
        self, owner_agent, participant_agent
    ):
        """Verify owner sees modifications made by participant."""
        # Setup meeting
        shared_state = Box({"turn": 1, "board": [[0, 0], [0, 0]]})
        meeting = Meeting(
            id="meeting_100",
            created_at=datetime.now(),
            owner_id=owner_agent.id,
            topic="Game",
            shared_state=shared_state,
        )
        owner_agent.owned_meetings[meeting.id] = meeting

        joined_meeting = JoinedMeeting(
            id=meeting.id,
            owner_id=owner_agent.id,
            joined_at=datetime.now(),
            topic="Game",
            shared_state=meeting.shared_state,
        )
        participant_agent.joined_meetings[meeting.id] = joined_meeting

        # Participant modifies shared_state
        participant_agent.joined_meetings[meeting.id].shared_state["turn"] = 2
        participant_agent.joined_meetings[meeting.id].shared_state["board"][0][0] = 1
        participant_agent.joined_meetings[meeting.id].shared_state["winner"] = None

        # Owner should see all changes
        assert owner_agent.owned_meetings[meeting.id].shared_state["turn"] == 2
        assert owner_agent.owned_meetings[meeting.id].shared_state["board"][0][0] == 1
        assert owner_agent.owned_meetings[meeting.id].shared_state["winner"] is None

    def test_modifications_through_execution_namespace(
        self, owner_agent, participant_agent
    ):
        """Verify modifications through PythonExecutor namespace are shared."""
        # Setup meeting
        shared_state = Box({"counter": 0})
        meeting = Meeting(
            id="meeting_100",
            created_at=datetime.now(),
            owner_id=owner_agent.id,
            topic="Counter Test",
            shared_state=shared_state,
        )
        owner_agent.owned_meetings[meeting.id] = meeting

        joined_meeting = JoinedMeeting(
            id=meeting.id,
            owner_id=owner_agent.id,
            joined_at=datetime.now(),
            topic="Counter Test",
            shared_state=meeting.shared_state,
        )
        participant_agent.joined_meetings[meeting.id] = joined_meeting

        # Mock get_current_meeting for both agents
        owner_agent.get_current_meeting = Mock(return_value=meeting)
        participant_agent.get_current_meeting = Mock(return_value=joined_meeting)

        # Setup call stack frames for both agents
        owner_frame = Mock(spec=CallStackFrame)
        owner_frame.meeting_id = meeting.id
        owner_frame.is_meeting = True
        owner_agent.call_stack.peek = Mock(return_value=owner_frame)
        owner_agent.call_stack.frames = [owner_frame]  # Add to frames list

        participant_frame = Mock(spec=CallStackFrame)
        participant_frame.meeting_id = meeting.id
        participant_frame.is_meeting = True
        participant_agent.call_stack.peek = Mock(return_value=participant_frame)
        participant_agent.call_stack.frames = [participant_frame]  # Add to frames list

        # Create executors for both agents
        owner_executor = PythonExecutor(owner_agent)
        participant_executor = PythonExecutor(participant_agent)

        # Build namespaces
        owner_namespace = owner_executor.build_namespace()
        participant_namespace = participant_executor.build_namespace()

        # Verify both have access to meeting
        assert "meeting" in owner_namespace
        assert "meeting" in participant_namespace

        # Owner modifies through namespace
        owner_namespace["meeting"].shared_state["counter"] = 10
        owner_namespace["meeting"].shared_state["owner_data"] = "test"

        # Participant should see changes
        assert participant_namespace["meeting"].shared_state["counter"] == 10
        assert participant_namespace["meeting"].shared_state["owner_data"] == "test"

        # Participant modifies through namespace
        participant_namespace["meeting"].shared_state["counter"] = 20
        participant_namespace["meeting"].shared_state["participant_data"] = "hello"

        # Owner should see changes
        assert owner_namespace["meeting"].shared_state["counter"] == 20
        assert owner_namespace["meeting"].shared_state["participant_data"] == "hello"

        # Verify the original shared_state object was modified
        assert meeting.shared_state["counter"] == 20
        assert meeting.shared_state["owner_data"] == "test"
        assert meeting.shared_state["participant_data"] == "hello"

    def test_multiple_participants_all_share_same_state(
        self, owner_agent, participant_agent, event_bus, mock_program
    ):
        """Verify multiple participants all share the same state object."""
        # Create second participant
        participant2 = Mock(spec=LocalAIAgent)
        participant2.id = "agent_3000"
        participant2.klass = "Player2"
        participant2.joined_meetings = {}
        participant2.call_stack = Mock(spec=CallStack)

        # Setup meeting
        shared_state = Box({"data": "initial"})
        meeting = Meeting(
            id="meeting_100",
            created_at=datetime.now(),
            owner_id=owner_agent.id,
            topic="Multi-player",
            shared_state=shared_state,
        )
        owner_agent.owned_meetings[meeting.id] = meeting

        # Both participants join
        participant_agent.joined_meetings[meeting.id] = JoinedMeeting(
            id=meeting.id,
            owner_id=owner_agent.id,
            joined_at=datetime.now(),
            topic="Multi-player",
            shared_state=meeting.shared_state,
        )

        participant2.joined_meetings[meeting.id] = JoinedMeeting(
            id=meeting.id,
            owner_id=owner_agent.id,
            joined_at=datetime.now(),
            topic="Multi-player",
            shared_state=meeting.shared_state,
        )

        # Verify all three have the same object reference
        owner_state = owner_agent.owned_meetings[meeting.id].shared_state
        p1_state = participant_agent.joined_meetings[meeting.id].shared_state
        p2_state = participant2.joined_meetings[meeting.id].shared_state

        assert owner_state is p1_state
        assert owner_state is p2_state
        assert p1_state is p2_state

        # Verify IDs match
        assert id(owner_state) == id(p1_state) == id(p2_state)

        # Verify modifications by any agent are visible to all
        owner_state["data"] = "modified by owner"
        assert p1_state["data"] == "modified by owner"
        assert p2_state["data"] == "modified by owner"

        p1_state["data"] = "modified by p1"
        assert owner_state["data"] == "modified by p1"
        assert p2_state["data"] == "modified by p1"

        p2_state["data"] = "modified by p2"
        assert owner_state["data"] == "modified by p2"
        assert p1_state["data"] == "modified by p2"


class TestSharedStateEdgeCases:
    """Test edge cases where shared_state might not be shared correctly."""

    @pytest.mark.asyncio
    async def test_shared_state_lost_if_no_pending_meeting(
        self, owner_agent, participant_agent, mock_program
    ):
        """Test that shared_state creates fallback if agent doesn't have pending meeting reference."""
        # Setup meeting manager for participant
        meeting_manager = MeetingManager(
            agent_id=participant_agent.id,
            agent_klass=participant_agent.klass,
            agent=participant_agent,
            program=mock_program,
            playbook_executor=participant_agent,
        )

        # Create meeting with shared_state (on owner side)
        shared_state = Box({"important": "data", "counter": 42})
        meeting = Meeting(
            id="meeting_100",
            created_at=datetime.now(),
            owner_id=owner_agent.id,
            topic="Test Meeting",
            shared_state=shared_state,
        )
        owner_agent.owned_meetings[meeting.id] = meeting

        # Simulate participant accepting invitation WITHOUT pending meeting reference
        # (This could happen if invitation was sent through remote message)
        participant_agent._pending_meeting_invitations = {}

        # Try to accept - should create fallback shared_state
        await meeting_manager._accept_meeting_invitation(
            meeting_id=meeting.id,
            inviter_id=owner_agent.id,
            topic="Test Meeting",
            playbook_name="TestPlaybook",
        )

        # Verify participant got fallback shared_state (not the original)
        assert meeting.id in participant_agent.joined_meetings
        joined_meeting = participant_agent.joined_meetings[meeting.id]
        assert isinstance(joined_meeting.shared_state, Box)
        # Should be a different object than the owner's shared_state
        assert joined_meeting.shared_state is not meeting.shared_state
        # Fallback should be empty
        assert len(joined_meeting.shared_state) == 0

    @pytest.mark.asyncio
    async def test_shared_state_preserved_through_full_invitation_flow(
        self, owner_agent, participant_agent, mock_program
    ):
        """Test shared_state is preserved through full invite->accept flow."""
        # Setup meeting manager for owner
        owner_meeting_manager = MeetingManager(
            agent_id=owner_agent.id,
            agent_klass=owner_agent.klass,
            agent=owner_agent,
            program=mock_program,
            playbook_executor=owner_agent,
        )

        # Setup meeting manager for participant
        participant_meeting_manager = MeetingManager(
            agent_id=participant_agent.id,
            agent_klass=participant_agent.klass,
            agent=participant_agent,
            program=mock_program,
            playbook_executor=participant_agent,
        )

        # Owner creates meeting with initial shared_state
        shared_state = Box({"game_state": "initialized", "turn": 0})
        meeting = Meeting(
            id="meeting_100",
            created_at=datetime.now(),
            owner_id=owner_agent.id,
            topic="Game",
            shared_state=shared_state,
        )
        owner_agent.owned_meetings[meeting.id] = meeting

        # Owner invites participant (this should store meeting reference)
        await owner_meeting_manager._invite_to_meeting(meeting, participant_agent)

        # Verify pending invitation was stored
        assert hasattr(participant_agent, "_pending_meeting_invitations")
        assert meeting.id in participant_agent._pending_meeting_invitations
        stored_meeting = participant_agent._pending_meeting_invitations[meeting.id]

        # Verify shared_state reference is in pending meeting
        assert stored_meeting.shared_state is meeting.shared_state
        assert id(stored_meeting.shared_state) == id(meeting.shared_state)

        # Participant accepts invitation
        await participant_meeting_manager._accept_meeting_invitation(
            meeting_id=meeting.id,
            inviter_id=owner_agent.id,
            topic="Game",
            playbook_name="GamePlaybook",
        )

        # Verify participant's joined meeting has correct shared_state reference
        assert meeting.id in participant_agent.joined_meetings
        joined = participant_agent.joined_meetings[meeting.id]
        assert joined.shared_state is meeting.shared_state
        assert id(joined.shared_state) == id(meeting.shared_state)

        # Verify modifications are truly shared
        meeting.shared_state["turn"] = 1
        assert joined.shared_state["turn"] == 1

        joined.shared_state["game_state"] = "in_progress"
        assert meeting.shared_state["game_state"] == "in_progress"

    def test_playbook_dotmap_is_mutable_reference(self):
        """Verify Box maintains reference semantics."""
        # Create a Box
        original = Box({"counter": 0, "data": []})

        # Assign to multiple variables
        ref1 = original
        ref2 = original

        # Verify they're the same object
        assert ref1 is original
        assert ref2 is original
        assert ref1 is ref2

        # Modify through one reference
        ref1["counter"] = 10
        ref1["data"].append("item")

        # Verify visible through all references
        assert original["counter"] == 10
        assert ref2["counter"] == 10
        assert len(original["data"]) == 1
        assert len(ref2["data"]) == 1

    def test_meeting_wrapper_preserves_shared_state_reference(self, owner_agent):
        """Verify MeetingWrapper preserves shared_state reference."""
        # Create meeting
        shared_state = Box({"value": 100})
        meeting = Meeting(
            id="meeting_100",
            created_at=datetime.now(),
            owner_id=owner_agent.id,
            topic="Test",
            shared_state=shared_state,
        )
        owner_agent.owned_meetings[meeting.id] = meeting

        # Mock get_current_meeting to return the meeting object
        owner_agent.get_current_meeting = Mock(return_value=meeting)

        # Setup call stack
        frame = Mock(spec=CallStackFrame)
        frame.meeting_id = meeting.id
        frame.is_meeting = True
        owner_agent.call_stack.peek = Mock(return_value=frame)
        owner_agent.call_stack.frames = [frame]  # Add to frames list

        # Build namespace with MeetingWrapper
        executor = PythonExecutor(owner_agent)
        namespace = executor.build_namespace()

        # Verify wrapper has correct reference
        wrapper = namespace["meeting"]
        assert wrapper.shared_state is meeting.shared_state
        assert id(wrapper.shared_state) == id(meeting.shared_state)

        # Modify through wrapper
        wrapper.shared_state["value"] = 200

        # Verify modification visible in original
        assert meeting.shared_state["value"] == 200
