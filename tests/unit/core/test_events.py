"""
Comprehensive tests for the unified event system.

Tests all event types and their properties to ensure the unified event system
works correctly with proper inheritance and field validation.
"""

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from playbooks.core.events import (
    AgentPausedEvent,
    AgentResumedEvent,
    AgentStartedEvent,
    AgentStepEvent,
    AgentStoppedEvent,
    BreakpointHitEvent,
    CallStackPopEvent,
    CallStackPushEvent,
    CompiledProgramEvent,
    Event,
    ExecutionPausedEvent,
    InstructionPointerEvent,
    LineExecutedEvent,
    PlaybookEndEvent,
    PlaybookStartEvent,
    ProgramTerminatedEvent,
    StepCompleteEvent,
    VariableUpdateEvent,
)


class TestEventBase:
    """Test the base Event class."""

    def test_event_creation_with_required_fields(self):
        """Test creating an event with required fields."""
        event = Event(session_id="test-session", agent_id="agent-1")

        assert event.session_id == "test-session"
        assert event.agent_id == "agent-1"
        assert isinstance(event.timestamp, datetime)

    def test_event_creation_with_defaults(self):
        """Test creating an event with default values."""
        event = Event(session_id="test-session")

        assert event.session_id == "test-session"
        assert event.agent_id == ""
        assert isinstance(event.timestamp, datetime)

    def test_event_is_frozen(self):
        """Test that events are immutable (frozen dataclasses)."""
        event = Event(session_id="test-session")

        with pytest.raises(FrozenInstanceError):
            event.session_id = "modified"

        with pytest.raises(FrozenInstanceError):
            event.agent_id = "modified"

    def test_event_timestamp_auto_generated(self):
        """Test that timestamp is automatically generated."""
        before = datetime.now()
        event = Event(session_id="test-session")
        after = datetime.now()

        assert before <= event.timestamp <= after


class TestProgramEvents:
    """Test program execution events."""

    def test_call_stack_push_event(self):
        """Test CallStackPushEvent creation and properties."""
        event = CallStackPushEvent(
            session_id="test-session",
            agent_id="agent-1",
            frame="main_function",
            stack=["main", "sub_function"],
        )

        assert event.session_id == "test-session"
        assert event.agent_id == "agent-1"
        assert event.frame == "main_function"
        assert event.stack == ["main", "sub_function"]
        assert isinstance(event.timestamp, datetime)

    def test_call_stack_push_event_defaults(self):
        """Test CallStackPushEvent with default values."""
        event = CallStackPushEvent(session_id="test-session")

        assert event.frame == ""
        assert event.stack == []

    def test_call_stack_pop_event(self):
        """Test CallStackPopEvent creation and properties."""
        event = CallStackPopEvent(
            session_id="test-session",
            agent_id="agent-1",
            frame="main_function",
            stack=["main"],
        )

        assert event.session_id == "test-session"
        assert event.agent_id == "agent-1"
        assert event.frame == "main_function"
        assert event.stack == ["main"]

    def test_instruction_pointer_event(self):
        """Test InstructionPointerEvent creation and properties."""
        event = InstructionPointerEvent(
            session_id="test-session",
            agent_id="agent-1",
            pointer="line:42",
            stack=["main", "sub"],
        )

        assert event.session_id == "test-session"
        assert event.agent_id == "agent-1"
        assert event.pointer == "line:42"
        assert event.stack == ["main", "sub"]

    def test_compiled_program_event(self):
        """Test CompiledProgramEvent creation and properties."""
        event = CompiledProgramEvent(
            session_id="test-session",
            agent_id="agent-1",
            compiled_file_path="test.pbasm",
            content="compiled content",
            original_file_paths=["test.pb", "lib.pb"],
        )

        assert event.session_id == "test-session"
        assert event.agent_id == "agent-1"
        assert event.compiled_file_path == "test.pbasm"
        assert event.content == "compiled content"
        assert event.original_file_paths == ["test.pb", "lib.pb"]

    def test_program_terminated_event(self):
        """Test ProgramTerminatedEvent creation and properties."""
        event = ProgramTerminatedEvent(
            session_id="test-session", agent_id="agent-1", reason="normal", exit_code=0
        )

        assert event.session_id == "test-session"
        assert event.agent_id == "agent-1"
        assert event.reason == "normal"
        assert event.exit_code == 0


class TestAgentEvents:
    """Test agent lifecycle events."""

    def test_agent_started_event(self):
        """Test AgentStartedEvent creation and properties."""
        event = AgentStartedEvent(
            session_id="test-session",
            agent_id="agent-1",
            agent_name="TestAgent",
            agent_type="ai",
        )

        assert event.session_id == "test-session"
        assert event.agent_id == "agent-1"
        assert event.agent_name == "TestAgent"
        assert event.agent_type == "ai"

    def test_agent_stopped_event(self):
        """Test AgentStoppedEvent creation and properties."""
        event = AgentStoppedEvent(
            session_id="test-session",
            agent_id="agent-1",
            agent_name="TestAgent",
            reason="normal",
        )

        assert event.session_id == "test-session"
        assert event.agent_id == "agent-1"
        assert event.agent_name == "TestAgent"
        assert event.reason == "normal"

    def test_agent_paused_event(self):
        """Test AgentPausedEvent creation and properties."""
        event = AgentPausedEvent(
            session_id="test-session",
            agent_id="agent-1",
            reason="breakpoint",
            source_line_number=42,
            step="step_over",
        )

        assert event.session_id == "test-session"
        assert event.agent_id == "agent-1"
        assert event.reason == "breakpoint"
        assert event.source_line_number == 42
        assert event.step == "step_over"

    def test_agent_resumed_event(self):
        """Test AgentResumedEvent creation and properties."""
        event = AgentResumedEvent(session_id="test-session", agent_id="agent-1")

        assert event.session_id == "test-session"
        assert event.agent_id == "agent-1"

    def test_agent_step_event(self):
        """Test AgentStepEvent creation and properties."""
        event = AgentStepEvent(
            session_id="test-session", agent_id="agent-1", step_mode="over"
        )

        assert event.session_id == "test-session"
        assert event.agent_id == "agent-1"
        assert event.step_mode == "over"


class TestDebugEvents:
    """Test debugging-specific events."""

    def test_breakpoint_hit_event(self):
        """Test BreakpointHitEvent creation and properties."""
        event = BreakpointHitEvent(
            session_id="test-session",
            agent_id="agent-1",
            file_path="test.py",
            line_number=42,
            source_line_number=45,
        )

        assert event.session_id == "test-session"
        assert event.agent_id == "agent-1"
        assert event.file_path == "test.py"
        assert event.line_number == 42
        assert event.source_line_number == 45

    def test_step_complete_event(self):
        """Test StepCompleteEvent creation and properties."""
        event = StepCompleteEvent(
            session_id="test-session", agent_id="agent-1", source_line_number=42
        )

        assert event.session_id == "test-session"
        assert event.agent_id == "agent-1"
        assert event.source_line_number == 42

    def test_variable_update_event(self):
        """Test VariableUpdateEvent creation and properties."""
        event = VariableUpdateEvent(
            session_id="test-session",
            agent_id="agent-1",
            variable_name="counter",
            variable_value=42,
        )

        assert event.session_id == "test-session"
        assert event.agent_id == "agent-1"
        assert event.variable_name == "counter"
        assert event.variable_value == 42

    def test_execution_paused_event(self):
        """Test ExecutionPausedEvent creation and properties."""
        event = ExecutionPausedEvent(
            session_id="test-session",
            agent_id="agent-1",
            reason="step",
            source_line_number=42,
            step="step_into",
        )

        assert event.session_id == "test-session"
        assert event.agent_id == "agent-1"
        assert event.reason == "step"
        assert event.source_line_number == 42
        assert event.step == "step_into"

    def test_line_executed_event(self):
        """Test LineExecutedEvent creation and properties."""
        event = LineExecutedEvent(
            session_id="test-session",
            agent_id="agent-1",
            step="step_over",
            source_line_number=42,
            text="print('hello')",
            file_path="test.py",
            line_number=45,
        )

        assert event.session_id == "test-session"
        assert event.agent_id == "agent-1"
        assert event.step == "step_over"
        assert event.source_line_number == 42
        assert event.text == "print('hello')"
        assert event.file_path == "test.py"
        assert event.line_number == 45


class TestPlaybookEvents:
    """Test playbook execution events."""

    def test_playbook_start_event(self):
        """Test PlaybookStartEvent creation and properties."""
        event = PlaybookStartEvent(
            session_id="test-session", agent_id="agent-1", playbook="test_playbook"
        )

        assert event.session_id == "test-session"
        assert event.agent_id == "agent-1"
        assert event.playbook == "test_playbook"

    def test_playbook_end_event(self):
        """Test PlaybookEndEvent creation and properties."""
        event = PlaybookEndEvent(
            session_id="test-session",
            agent_id="agent-1",
            playbook="test_playbook",
            return_value="success",
            call_stack_depth=3,
        )

        assert event.session_id == "test-session"
        assert event.agent_id == "agent-1"
        assert event.playbook == "test_playbook"
        assert event.return_value == "success"
        assert event.call_stack_depth == 3


class TestEventInheritance:
    """Test that all events properly inherit from Event base class."""

    @pytest.mark.parametrize(
        "event_class",
        [
            CallStackPushEvent,
            CallStackPopEvent,
            InstructionPointerEvent,
            CompiledProgramEvent,
            ProgramTerminatedEvent,
            AgentStartedEvent,
            AgentStoppedEvent,
            AgentPausedEvent,
            AgentResumedEvent,
            AgentStepEvent,
            BreakpointHitEvent,
            StepCompleteEvent,
            VariableUpdateEvent,
            ExecutionPausedEvent,
            LineExecutedEvent,
            PlaybookStartEvent,
            PlaybookEndEvent,
        ],
    )
    def test_event_inheritance(self, event_class):
        """Test that all event classes inherit from Event."""
        assert issubclass(event_class, Event)

    @pytest.mark.parametrize(
        "event_class",
        [
            CallStackPushEvent,
            CallStackPopEvent,
            InstructionPointerEvent,
            CompiledProgramEvent,
            ProgramTerminatedEvent,
            AgentStartedEvent,
            AgentStoppedEvent,
            AgentPausedEvent,
            AgentResumedEvent,
            AgentStepEvent,
            BreakpointHitEvent,
            StepCompleteEvent,
            VariableUpdateEvent,
            ExecutionPausedEvent,
            LineExecutedEvent,
            PlaybookStartEvent,
            PlaybookEndEvent,
        ],
    )
    def test_all_events_have_base_fields(self, event_class):
        """Test that all events have the base Event fields."""
        # Create instance with minimal required fields
        event = event_class(session_id="test")

        # All events should have these base fields
        assert hasattr(event, "session_id")
        assert hasattr(event, "agent_id")
        assert hasattr(event, "timestamp")

        assert event.session_id == "test"
        assert event.agent_id == ""  # default value
        assert isinstance(event.timestamp, datetime)
