"""Meeting system tests - progressive complexity from basic to tic-tac-toe game."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from playbooks.agents.local_ai_agent import LocalAIAgent
from playbooks.event_bus import EventBus
from playbooks.execution_state import ExecutionState
from playbooks.meetings import Meeting, MeetingRegistry
from playbooks.program import Program


# ============================================================================
# LEVEL 1: Basic Meeting Functionality Tests
# ============================================================================


@pytest.mark.asyncio
async def test_meeting_registry_generates_unique_ids():
    """Test that meeting registry generates sequential unique IDs."""
    registry = MeetingRegistry()

    id1 = registry.generate_meeting_id("agent1")
    id2 = registry.generate_meeting_id("agent2")
    id3 = registry.generate_meeting_id("agent1")

    assert id1 == "100"
    assert id2 == "101"
    assert id3 == "102"
    assert registry.get_meeting_owner(id1) == "agent1"
    assert registry.get_meeting_owner(id2) == "agent2"


@pytest.mark.asyncio
async def test_meeting_data_structure():
    """Test basic Meeting data structure functionality."""
    from datetime import datetime

    meeting = Meeting(
        meeting_id="100",
        initiator_id="host",
        participants={"host": "GameHost"},
        created_at=datetime.now(),
        topic="Game Setup",
    )

    # Test adding participants
    meeting.add_participant("player1", "Player")
    assert meeting.is_participant("player1")
    assert meeting.participants["player1"] == "Player"

    # Test removing participants
    meeting.remove_participant("player1")
    assert not meeting.is_participant("player1")
    assert "player1" not in meeting.participants


@pytest.mark.asyncio
async def test_meeting_manager_creates_meeting():
    """Test that MeetingManager can create meetings."""
    from playbooks.meetings import MeetingManager

    manager = MeetingManager("agent1", "TestAgent")
    registry = MeetingRegistry()

    meeting_id = await manager.create_meeting(
        invited_agents=["Player1", "Player2"],
        topic="Test Game",
        meeting_registry=registry,
    )

    assert meeting_id == "100"
    meeting = manager.get_meeting(meeting_id)
    assert meeting is not None
    assert meeting.topic == "Test Game"
    assert meeting.participants["agent1"] == "TestAgent"
    assert "Player1" in meeting.pending_invitations
    assert "Player2" in meeting.pending_invitations


# ============================================================================
# LEVEL 2: Meeting Message Exchange Tests
# ============================================================================


@pytest.mark.asyncio
async def test_meeting_message_handling():
    """Test message handling in meetings."""
    from datetime import datetime
    from playbooks.meetings import MeetingMessageHandler

    handler = MeetingMessageHandler("agent1", "TestAgent")
    meeting = Meeting(
        meeting_id="100",
        initiator_id="agent1",
        participants={"agent1": "TestAgent", "agent2": "Player"},
        created_at=datetime.now(),
    )
    owned_meetings = {"100": meeting}
    session_log = []

    # Test handling meeting message
    result = await handler.handle_meeting_message(
        "agent2", "MEETING:100:Hello from player!", owned_meetings, session_log
    )

    assert result is True
    assert len(meeting.message_history) == 1
    assert meeting.message_history[0].content == "Hello from player!"
    assert meeting.message_history[0].sender_id == "agent2"


@pytest.mark.asyncio
async def test_meeting_broadcast():
    """Test broadcasting messages to meeting participants."""
    from datetime import datetime
    from playbooks.meetings import Meeting, MeetingMessageHandler

    handler = MeetingMessageHandler("host", "GameHost")
    meeting = Meeting(
        meeting_id="100",
        initiator_id="host",
        participants={"host": "GameHost", "player1": "Player", "player2": "Player"},
        created_at=datetime.now(),
    )
    owned_meetings = {"100": meeting}
    session_log = []

    # Mock route_message callback
    routed_messages = []

    async def mock_route_message(sender_id, target_id, message, **kwargs):
        routed_messages.append((sender_id, target_id, message))

    await handler.broadcast_to_meeting(
        "100", "Game started!", owned_meetings, mock_route_message, session_log
    )

    # Should send to both players but not back to host
    assert len(routed_messages) == 2
    assert any(target == "player1" for _, target, _ in routed_messages)
    assert any(target == "player2" for _, target, _ in routed_messages)
    assert all(
        "MEETING:100:Game started!" in message for _, _, message in routed_messages
    )


# ============================================================================
# LEVEL 3: Multi-Participant Meeting Tests
# ============================================================================


@pytest.mark.asyncio
async def test_meeting_invitation_flow():
    """Test complete meeting invitation and acceptance flow."""
    event_bus = EventBus(session_id="test_session")

    # Create host agent
    class HostAgent(LocalAIAgent):
        klass = "GameHost"
        description = "Game host"
        playbooks = {}

    host = HostAgent(event_bus=event_bus, agent_id="host")
    host.state = ExecutionState(event_bus=event_bus)

    # Create player agent
    class PlayerAgent(LocalAIAgent):
        klass = "Player"
        description = "Game player"
        playbooks = {}

    player = PlayerAgent(event_bus=event_bus, agent_id="player1")
    player.state = ExecutionState(event_bus=event_bus)

    # Set up meeting registry
    registry = MeetingRegistry()

    # Host creates meeting
    meeting_id = await host.meeting_manager.create_meeting(
        invited_agents=["Player"], topic="Tic-Tac-Toe Game", meeting_registry=registry
    )

    assert meeting_id == "100"
    meeting = host.meeting_manager.get_meeting(meeting_id)
    assert meeting.topic == "Tic-Tac-Toe Game"
    assert meeting.is_participant(host.id)  # Use actual agent ID
    assert "Player" in meeting.pending_invitations


@pytest.mark.asyncio
async def test_meeting_participant_management():
    """Test adding and removing participants from meetings."""
    from datetime import datetime

    # Create meeting with host
    meeting = Meeting(
        meeting_id="100",
        initiator_id="host",
        participants={"host": "GameHost"},
        created_at=datetime.now(),
        topic="Tic-Tac-Toe",
    )

    # Add players
    meeting.add_participant("player1", "Player")
    meeting.add_participant("player2", "Player")

    assert len(meeting.participants) == 3
    assert meeting.is_participant("player1")
    assert meeting.is_participant("player2")

    # Remove a player
    meeting.remove_participant("player2")
    assert len(meeting.participants) == 2
    assert not meeting.is_participant("player2")


# ============================================================================
# LEVEL 4: Integration Test - Tic-Tac-Toe Game
# ============================================================================


@pytest.mark.asyncio
async def test_example_two_player_game():
    """Test a complete tic-tac-toe game using the meeting system."""
    event_bus = EventBus(session_id="tic_tac_toe_game")

    # Create program with meeting registry - use minimal program content
    program = Program.__new__(Program)  # Create without calling __init__
    program.event_bus = event_bus
    program.meeting_id_registry = MeetingRegistry()
    program.agents = []
    program.agents_by_id = {}
    program.agents_by_klass = {}

    # Create game host agent
    class GameHostAgent(LocalAIAgent):
        klass = "GameHost"
        description = "Manages tic-tac-toe games"
        playbooks = {}

    host = GameHostAgent(event_bus=event_bus, agent_id="host")
    host.state = ExecutionState(event_bus=event_bus)
    host.program = program

    # Create player agents
    class PlayerAgent(LocalAIAgent):
        klass = "Player"
        description = "Plays tic-tac-toe"
        playbooks = {}

    player1 = PlayerAgent(event_bus=event_bus, agent_id="player1")
    player1.state = ExecutionState(event_bus=event_bus)
    player1.program = program

    player2 = PlayerAgent(event_bus=event_bus, agent_id="player2")
    player2.state = ExecutionState(event_bus=event_bus)
    player2.program = program

    # Set up program agents
    program.agents_by_id = {"host": host, "player1": player1, "player2": player2}
    program.agents_by_klass = {"GameHost": [host], "Player": [player1, player2]}

    # Mock game state
    game_board = [" "] * 9  # 3x3 tic-tac-toe board
    game_messages = []

    # Track all routed messages
    async def capture_route_message(sender_id, target_spec, message, **kwargs):
        game_messages.append(
            {
                "sender": sender_id,
                "target": target_spec,
                "message": message,
                "kwargs": kwargs,
            }
        )

    program.route_message = capture_route_message

    # 1. Host creates game meeting
    meeting_id = await host.meeting_manager.create_meeting(
        invited_agents=["player1", "player2"],
        topic="Tic-Tac-Toe Game",
        meeting_registry=program.meeting_id_registry,
    )

    assert meeting_id == "100"
    meeting = host.meeting_manager.get_meeting(meeting_id)
    assert meeting.topic == "Tic-Tac-Toe Game"

    # 2. Players join meeting (simulate invitation acceptance)
    meeting.add_participant("player1", "Player")
    meeting.add_participant("player2", "Player")

    # 3. Host broadcasts game start
    await host.meeting_message_handler.broadcast_to_meeting(
        meeting_id,
        f"Welcome to Tic-Tac-Toe! Player1 is X, Player2 is O. Board: {' '.join(game_board)}",
        host.meeting_manager.owned_meetings,
        program.route_message,
        host.state.session_log,
    )

    # 4. Simulate game moves
    moves = [
        ("player1", 0, "X"),  # Player1 moves to position 0
        ("player2", 1, "O"),  # Player2 moves to position 1
        ("player1", 3, "X"),  # Player1 moves to position 3
        ("player2", 4, "O"),  # Player2 moves to position 4
        ("player1", 6, "X"),  # Player1 moves to position 6 - WINS! (vertical)
    ]

    winner = None
    for player_id, position, symbol in moves:
        # Player makes move
        game_board[position] = symbol

        # Player broadcasts move
        if player_id == "player1":
            await player1.meeting_message_handler.broadcast_to_meeting(
                meeting_id,
                f"I place {symbol} at position {position}. Board: {' '.join(game_board)}",
                {"100": meeting} if player_id == "player1" else {},
                program.route_message,
                player1.state.session_log,
            )

        # Check for winner (simple vertical check for position 0,3,6)
        if game_board[0] == game_board[3] == game_board[6] != " ":
            winner = player_id
            break

    # 5. Host announces winner
    if winner:
        await host.meeting_message_handler.broadcast_to_meeting(
            meeting_id,
            f"Game Over! {winner} wins with three in a column!",
            host.meeting_manager.owned_meetings,
            program.route_message,
            host.state.session_log,
        )

    # Verify the game flow
    assert len(game_messages) > 0
    assert winner == "player1"
    assert game_board == ["X", "O", " ", "X", "O", " ", "X", " ", " "]

    # Verify meeting has message history
    assert len(meeting.message_history) > 0

    # Verify all participants are in meeting
    assert meeting.is_participant(host.id)
    assert meeting.is_participant("player1")
    assert meeting.is_participant("player2")

    print(f"🎮 Tic-Tac-Toe game completed! Winner: {winner}")
    print(f"📋 Final board: {game_board}")
    print(f"💬 Total messages exchanged: {len(game_messages)}")


# ============================================================================
# Keep the working basic tests from the original file
# ============================================================================


@pytest.mark.asyncio
async def test_requester_filtering_kwargs_attendees():
    """Test that requester is filtered out from required attendees when using kwargs."""
    event_bus = EventBus(session_id="test_session")

    class TestAgent(LocalAIAgent):
        klass = "TestAgent"
        description = "Test agent"
        playbooks = {}

    agent = TestAgent(event_bus=event_bus)
    agent.state = ExecutionState(event_bus=event_bus)

    # Mock the required methods
    agent.get_playbook_attendees = MagicMock(
        return_value=(["TestAgent", "OtherAgent"], ["ThirdAgent"])
    )
    agent.create_meeting = AsyncMock(return_value="meeting_123")
    agent._wait_for_required_attendees = AsyncMock()

    # Test kwargs attendees (should filter out requester)
    kwargs = {"attendees": ["TestAgent", "RequiredAgent", "AnotherAgent"]}
    await agent._initialize_meeting_playbook("TestPlaybook", kwargs)

    # Check that _wait_for_required_attendees was called with requester filtered out
    call_args = agent._wait_for_required_attendees.call_args
    meeting_id, required_attendees = call_args[0]

    # Verify requester was filtered out
    assert meeting_id == "meeting_123"
    assert "TestAgent" not in required_attendees
    assert "RequiredAgent" in required_attendees
    assert "AnotherAgent" in required_attendees
    assert len(required_attendees) == 2


@pytest.mark.asyncio
async def test_ensure_meeting_playbook_kwargs():
    """Test that meeting playbooks get topic and attendees parameters added automatically."""
    from playbooks.meetings import MeetingManager
    from playbooks.playbook import MarkdownPlaybook

    # Create test playbooks with different signatures
    test_cases = [
        ("GameRoom() -> None", "GameRoom(topic: str, attendees: List[str]) -> None"),
        (
            "TaxPrepMeeting($form: str) -> None",
            "TaxPrepMeeting($form: str, topic: str, attendees: List[str]) -> None",
        ),
        (
            "Meeting(topic: str) -> None",
            "Meeting(topic: str, attendees: List[str]) -> None",
        ),
        (
            "Meeting(attendees: List[str]) -> None",
            "Meeting(attendees: List[str], topic: str) -> None",
        ),
        (
            "Meeting(topic: str, attendees: List[str]) -> None",
            "Meeting(topic: str, attendees: List[str]) -> None",
        ),
    ]

    manager = MeetingManager("agent1", "TestAgent")

    for original_sig, expected_sig in test_cases:
        # Create mock playbook
        playbook = MagicMock(spec=MarkdownPlaybook)
        playbook.meeting = True
        playbook.signature = original_sig

        playbooks = {"TestPlaybook": playbook}

        # Test the method
        manager.ensure_meeting_playbook_kwargs(playbooks)

        # Verify signature was updated correctly
        assert (
            playbook.signature == expected_sig
        ), f"Failed for {original_sig}: got {playbook.signature}, expected {expected_sig}"


@pytest.mark.asyncio
async def test_state_representation_includes_meetings():
    """Test that ExecutionState.to_dict() includes meetings list."""
    from datetime import datetime

    event_bus = EventBus(session_id="test_session")
    state = ExecutionState(event_bus=event_bus)

    # Add a test meeting
    meeting = Meeting(
        meeting_id="123",
        initiator_id="agent1000",
        participants={"agent1000": "TestAgent", "agent1001": "AssistantAgent"},
        created_at=datetime.now(),
        topic="Test Meeting",
    )
    state.owned_meetings["123"] = meeting

    # Test state representation
    state_dict = state.to_dict()

    # Verify meetings are included
    assert "meetings" in state_dict
    assert len(state_dict["meetings"]) == 1

    meeting_dict = state_dict["meetings"][0]
    assert meeting_dict["meeting_id"] == "123"
    assert len(meeting_dict["participants"]) == 2

    # Verify participants format (they are strings like "TestAgent(agent agent1000)")
    participants = meeting_dict["participants"]
    assert len(participants) == 2

    # Check that both participants are present in the formatted strings
    participant_string = " ".join(participants)
    assert "TestAgent" in participant_string
    assert "AssistantAgent" in participant_string
    assert "agent1000" in participant_string
    assert "agent1001" in participant_string
