"""Unit tests for ExecutionState delta compression functionality."""

import pytest

from playbooks.state.call_stack import CallStackFrame, InstructionPointer
from playbooks.infrastructure.event_bus import EventBus
from playbooks.state.execution_state import ExecutionState
from playbooks.execution.step import PlaybookStep


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus("test_session")


@pytest.fixture
def execution_state(event_bus):
    """Create an execution state for testing."""
    return ExecutionState(event_bus, "TestAgent", "1000")


class TestExecutionStateDelta:
    """Test suite for ExecutionState delta compression."""

    def test_initial_state_has_no_delta(self, execution_state):
        """Test that initial state has no last_sent_state."""
        assert execution_state.last_sent_state is None
        assert execution_state.last_i_frame_execution_id is None

    def test_full_state_returns_complete_state(self, execution_state):
        """Test that to_dict(full=True) returns complete state."""
        # Add some state
        execution_state.variables["$var1"] = "value1"
        execution_state.agents = [{"id": "1001", "name": "Agent1"}]

        full_state = execution_state.to_dict(full=True)

        assert "call_stack" in full_state
        assert "variables" in full_state
        assert "agents" in full_state
        assert "owned_meetings" in full_state
        assert "joined_meetings" in full_state
        assert "_format" not in full_state

    def test_delta_without_last_sent_state_returns_full(self, execution_state):
        """Test that delta without last_sent_state returns full state."""
        execution_state.variables["$var1"] = "value1"

        # Request delta but no last_sent_state
        delta = execution_state.to_dict(full=False)

        # Should return full state since no baseline
        assert "_format" not in delta
        assert "variables" in delta

    def test_delta_with_no_changes(self, execution_state):
        """Test delta when nothing has changed."""
        execution_state.variables["$var1"] = "value1"
        execution_state.last_sent_state = execution_state.to_dict(full=True)

        # Get delta with no changes
        delta = execution_state.to_dict(full=False)

        # No changes should return None
        assert delta is None

    def test_delta_with_added_variables(self, execution_state):
        """Test delta when variables are added."""
        execution_state.variables["$var1"] = "value1"
        execution_state.last_sent_state = execution_state.to_dict(full=True)

        # Add new variable
        execution_state.variables["$var2"] = "value2"

        delta = execution_state.to_dict(full=False)

        assert delta is not None
        assert "new_variables" in delta
        assert "$var2" in delta["new_variables"]
        assert delta["new_variables"]["$var2"] == "value2"
        assert "changed_variables" not in delta
        assert "deleted_variables" not in delta

    def test_delta_with_modified_variables(self, execution_state):
        """Test delta when variables are modified."""
        execution_state.variables["$var1"] = "value1"
        execution_state.last_sent_state = execution_state.to_dict(full=True)

        # Modify existing variable
        execution_state.variables["$var1"] = "new_value"

        delta = execution_state.to_dict(full=False)

        assert delta is not None
        assert "changed_variables" in delta
        assert "$var1" in delta["changed_variables"]
        assert delta["changed_variables"]["$var1"] == "new_value"
        assert "new_variables" not in delta
        assert "deleted_variables" not in delta

    def test_delta_with_deleted_variables(self, execution_state):
        """Test delta when variables are deleted."""
        execution_state.variables["$var1"] = "value1"
        execution_state.variables["$var2"] = "value2"
        execution_state.last_sent_state = execution_state.to_dict(full=True)

        # Delete a variable
        execution_state.variables.variables.pop("$var2")

        delta = execution_state.to_dict(full=False)

        assert delta is not None
        assert "deleted_variables" in delta
        assert "$var2" in delta["deleted_variables"]
        assert "new_variables" not in delta
        assert "changed_variables" not in delta

    def test_delta_with_mixed_variable_changes(self, execution_state):
        """Test delta with added, modified, and deleted variables."""
        execution_state.variables["$var1"] = "value1"
        execution_state.variables["$var2"] = "value2"
        execution_state.last_sent_state = execution_state.to_dict(full=True)

        # Add, modify, delete
        execution_state.variables["$var3"] = "value3"  # add
        execution_state.variables["$var1"] = "modified1"  # modify
        execution_state.variables.variables.pop("$var2")  # delete

        delta = execution_state.to_dict(full=False)

        assert delta is not None
        assert "new_variables" in delta
        assert "$var3" in delta["new_variables"]
        assert "changed_variables" in delta
        assert "$var1" in delta["changed_variables"]
        assert "deleted_variables" in delta
        assert "$var2" in delta["deleted_variables"]

    def test_delta_with_new_agents(self, execution_state):
        """Test delta when new agents are added."""
        execution_state.agents = [{"id": "1001", "name": "Agent1"}]
        execution_state.last_sent_state = execution_state.to_dict(full=True)

        # Add new agent
        execution_state.agents.append({"id": "1002", "name": "Agent2"})

        delta = execution_state.to_dict(full=False)

        assert delta is not None
        assert "new_agents" in delta
        assert len(delta["new_agents"]) == 1
        assert delta["new_agents"][0]["id"] == "1002"

    def test_delta_with_call_stack_changes(self, execution_state):
        """Test delta when call stack changes."""
        # Initial call stack
        step = PlaybookStep("01", "EXE", "Do something", "- 01:EXE Do something")
        ip = InstructionPointer("Playbook1", "01", 1, step)
        frame = CallStackFrame(ip)
        execution_state.call_stack.push(frame)

        execution_state.last_sent_state = execution_state.to_dict(full=True)

        # Add another frame
        step2 = PlaybookStep(
            "02", "EXE", "Do something else", "- 02:EXE Do something else"
        )
        ip2 = InstructionPointer("Playbook1", "02", 2, step2)
        frame2 = CallStackFrame(ip2)
        execution_state.call_stack.push(frame2)

        delta = execution_state.to_dict(full=False)

        assert delta is not None
        assert "call_stack" in delta
        assert len(delta["call_stack"]) == 2

    def test_delta_with_no_call_stack_changes(self, execution_state):
        """Test delta when call stack hasn't changed."""
        # Initial call stack
        step = PlaybookStep("01", "EXE", "Do something", "- 01:EXE Do something")
        ip = InstructionPointer("Playbook1", "01", 1, step)
        frame = CallStackFrame(ip)
        execution_state.call_stack.push(frame)

        execution_state.last_sent_state = execution_state.to_dict(full=True)

        # No changes
        delta = execution_state.to_dict(full=False)

        # Should return None for empty delta
        assert delta is None

    def test_compute_variable_delta_handles_complex_values(self, execution_state):
        """Test delta computation with complex variable values."""
        execution_state.variables["$list"] = [1, 2, 3]
        execution_state.variables["$dict"] = {"key": "value"}
        execution_state.last_sent_state = execution_state.to_dict(full=True)

        # Modify complex values
        execution_state.variables["$list"] = [1, 2, 3, 4]
        execution_state.variables["$dict"] = {"key": "new_value"}

        delta = execution_state.to_dict(full=False)

        assert delta is not None
        assert "changed_variables" in delta
        assert "$list" in delta["changed_variables"]
        assert "$dict" in delta["changed_variables"]

    def test_empty_delta_returns_none(self, execution_state):
        """Test that empty delta returns None."""
        execution_state.variables["$var1"] = "value1"
        execution_state.last_sent_state = execution_state.to_dict(full=True)

        # No changes
        delta = execution_state.to_dict(full=False)

        assert delta is None

    def test_full_state_update_resets_baseline(self, execution_state):
        """Test that requesting full state can reset the baseline."""
        execution_state.variables["$var1"] = "value1"
        execution_state.last_sent_state = execution_state.to_dict(full=True)

        # Add variable
        execution_state.variables["$var2"] = "value2"

        # Get full state
        full_state = execution_state.to_dict(full=True)

        # Update baseline
        execution_state.last_sent_state = full_state

        # Now delta should show no changes (returns None)
        delta = execution_state.to_dict(full=False)

        assert delta is None


class TestGetStateForLLM:
    """Test suite for get_state_for_llm method."""

    def test_first_call_returns_full_state(self, execution_state):
        """Test that first call returns full state."""
        from playbooks.config import StateCompressionConfig
        from playbooks.llm.messages.types import FrameType

        execution_state.variables["$var1"] = "value1"
        compression_config = StateCompressionConfig(
            enabled=True, full_state_interval=10
        )

        state_dict, frame_type = execution_state.get_state_for_llm(
            1, compression_config
        )

        assert state_dict is not None
        assert frame_type == FrameType.I
        assert "variables" in state_dict  # Full state has "variables" key
        assert execution_state.last_i_frame_execution_id == 1
        assert execution_state.last_sent_state is not None

    def test_second_call_returns_delta(self, execution_state):
        """Test that second call returns delta."""
        from playbooks.config import StateCompressionConfig
        from playbooks.llm.messages.types import FrameType

        compression_config = StateCompressionConfig(
            enabled=True, full_state_interval=10
        )

        # First call
        execution_state.variables["$var1"] = "value1"
        state_dict, frame_type = execution_state.get_state_for_llm(
            1, compression_config
        )
        assert frame_type == FrameType.I

        # Second call with changes
        execution_state.variables["$var2"] = "value2"
        state_dict, frame_type = execution_state.get_state_for_llm(
            2, compression_config
        )

        assert state_dict is not None
        assert frame_type == FrameType.P
        assert "new_variables" in state_dict
        assert "$var2" in state_dict["new_variables"]

    def test_second_call_with_no_changes_returns_none(self, execution_state):
        """Test that second call with no changes returns None."""
        from playbooks.config import StateCompressionConfig
        from playbooks.llm.messages.types import FrameType

        compression_config = StateCompressionConfig(
            enabled=True, full_state_interval=10
        )

        # First call
        execution_state.variables["$var1"] = "value1"
        state_dict, frame_type = execution_state.get_state_for_llm(
            1, compression_config
        )

        # Second call with NO changes
        state_dict, frame_type = execution_state.get_state_for_llm(
            2, compression_config
        )

        assert state_dict is None  # No changes
        assert frame_type == FrameType.P

    def test_interval_triggers_full_state(self, execution_state):
        """Test that interval triggers full state."""
        from playbooks.config import StateCompressionConfig
        from playbooks.llm.messages.types import FrameType

        compression_config = StateCompressionConfig(enabled=True, full_state_interval=3)

        # First call
        execution_state.variables["$var1"] = "value1"
        state_dict, frame_type = execution_state.get_state_for_llm(
            1, compression_config
        )
        assert frame_type == FrameType.I

        # Calls 2-3 should be P-frames
        execution_state.variables["$var2"] = "value2"
        state_dict, frame_type = execution_state.get_state_for_llm(
            2, compression_config
        )
        assert frame_type == FrameType.P

        execution_state.variables["$var3"] = "value3"
        state_dict, frame_type = execution_state.get_state_for_llm(
            3, compression_config
        )
        assert frame_type == FrameType.P

        # Call 4 should be I-frame (interval reached)
        execution_state.variables["$var4"] = "value4"
        state_dict, frame_type = execution_state.get_state_for_llm(
            4, compression_config
        )
        assert frame_type == FrameType.I
        assert state_dict is not None
        assert "variables" in state_dict  # Full state
        assert execution_state.last_i_frame_execution_id == 4

    def test_compression_disabled_always_returns_full(self, execution_state):
        """Test that disabled compression always returns full state."""
        from playbooks.config import StateCompressionConfig
        from playbooks.llm.messages.types import FrameType

        compression_config = StateCompressionConfig(
            enabled=False, full_state_interval=10
        )

        # First call
        execution_state.variables["$var1"] = "value1"
        state_dict, frame_type = execution_state.get_state_for_llm(
            1, compression_config
        )
        assert frame_type == FrameType.I
        assert "variables" in state_dict

        # Second call should also be full
        execution_state.variables["$var2"] = "value2"
        state_dict, frame_type = execution_state.get_state_for_llm(
            2, compression_config
        )
        assert frame_type == FrameType.I
        assert "variables" in state_dict

    def test_none_execution_id_returns_full(self, execution_state):
        """Test that None execution_id returns full state."""
        from playbooks.config import StateCompressionConfig
        from playbooks.llm.messages.types import FrameType

        compression_config = StateCompressionConfig(
            enabled=True, full_state_interval=10
        )

        execution_state.variables["$var1"] = "value1"
        state_dict, frame_type = execution_state.get_state_for_llm(
            None, compression_config
        )

        assert state_dict is not None
        assert frame_type == FrameType.I
        assert "variables" in state_dict

    def test_uses_default_config_when_none(self, execution_state):
        """Test that default config is used when none provided."""
        from playbooks.llm.messages.types import FrameType

        execution_state.variables["$var1"] = "value1"

        # Should use global config
        state_dict, frame_type = execution_state.get_state_for_llm(1, None)

        # Should return a state (either full or delta depending on global config)
        assert isinstance(state_dict, dict) or state_dict is None
        assert frame_type in [FrameType.I, FrameType.P]


class TestStateCompressionMessageCompactionCoordination:
    """Test suite for coordination between state compression and message compaction."""

    def test_i_frame_message_has_frame_type(self):
        """Test that I-frame messages have frame_type set."""
        from playbooks.llm.messages.types import FrameType, UserInputLLMMessage

        msg = UserInputLLMMessage("test content", frame_type=FrameType.I)

        assert msg.frame_type == FrameType.I

    def test_p_frame_message_has_frame_type(self):
        """Test that P-frame messages have frame_type set."""
        from playbooks.llm.messages.types import FrameType, UserInputLLMMessage

        msg = UserInputLLMMessage("test content", frame_type=FrameType.P)

        assert msg.frame_type == FrameType.P

    def test_default_frame_type_is_i(self):
        """Test that default frame_type is I."""
        from playbooks.llm.messages.types import FrameType, UserInputLLMMessage

        msg = UserInputLLMMessage("test content")

        assert msg.frame_type == FrameType.I

    def test_compactor_preserves_last_i_frame(self):
        """Test that compactor preserves the last I-frame."""
        from playbooks.llm.llm_context_compactor import LLMContextCompactor
        from playbooks.llm.messages.types import (
            AssistantResponseLLMMessage,
            FrameType,
            UserInputLLMMessage,
        )

        # Create message sequence with I-frames and P-frames
        messages = [
            UserInputLLMMessage(
                "message 1", frame_type=FrameType.I
            ),  # I-frame at index 0
            AssistantResponseLLMMessage("response 1"),
            UserInputLLMMessage("message 2", frame_type=FrameType.P),  # P-frame
            AssistantResponseLLMMessage("response 2"),
            UserInputLLMMessage("message 3", frame_type=FrameType.P),  # P-frame
            AssistantResponseLLMMessage("response 3"),
            UserInputLLMMessage(
                "message 4", frame_type=FrameType.I
            ),  # I-frame at index 6 (most recent)
            AssistantResponseLLMMessage("response 4"),
            UserInputLLMMessage("message 5", frame_type=FrameType.P),  # P-frame
            AssistantResponseLLMMessage("response 5"),
        ]

        compactor = LLMContextCompactor()
        compacted = compactor.compact_messages(messages)

        # The last I-frame (message 4 at original index 6) should be preserved as full message
        # Count how many UserInput messages we have in compacted output
        user_messages_in_output = [m for m in compacted if m.get("role") == "user"]

        # We should have at least the last I-frame and subsequent P-frame preserved
        # UserInputLLMMessage.to_compact_message() returns None, so compacted user messages
        # would be removed. Only messages after safe_index are kept as full.
        # We expect message 4 (I-frame) and message 5 (P-frame) to be in full form
        assert len(user_messages_in_output) >= 1

        # Check that message 4 content is in the output
        message_4_found = any(
            m.get("content") == "message 4" for m in user_messages_in_output
        )
        assert (
            message_4_found
        ), f"I-frame 'message 4' should be preserved. Got: {user_messages_in_output}"

    def test_compactor_without_i_frames(self):
        """Test compactor behavior when no I-frames are present."""
        from playbooks.llm.llm_context_compactor import LLMContextCompactor
        from playbooks.llm.messages.types import (
            AssistantResponseLLMMessage,
            FrameType,
            UserInputLLMMessage,
        )

        # All P-frames (unlikely but possible)
        messages = [
            UserInputLLMMessage("message 1", frame_type=FrameType.P),
            AssistantResponseLLMMessage("response 1"),
            UserInputLLMMessage("message 2", frame_type=FrameType.P),
            AssistantResponseLLMMessage("response 2"),
        ]

        compactor = LLMContextCompactor()
        compacted = compactor.compact_messages(messages)

        # Should still compact based on normal rules (min_preserved_assistant_messages)
        assert len(compacted) > 0

    def test_empty_delta_produces_p_frame(self, execution_state):
        """Test that empty delta still produces P-frame marker."""
        from playbooks.config import StateCompressionConfig
        from playbooks.llm.messages.types import FrameType

        compression_config = StateCompressionConfig(
            enabled=True, full_state_interval=10
        )

        # First call - I-frame
        execution_state.variables["$var1"] = "value1"
        state_dict, frame_type = execution_state.get_state_for_llm(
            1, compression_config
        )
        assert frame_type == FrameType.I

        # Second call with NO changes - should be P-frame with None state
        state_dict, frame_type = execution_state.get_state_for_llm(
            2, compression_config
        )
        assert state_dict is None
        assert frame_type == FrameType.P  # Still P-frame, just empty


class TestDeltaCompressionEdgeCases:
    """Test suite for edge cases in delta compression."""

    def test_delta_with_meetings_changes(self, execution_state):
        """Test delta when meetings change."""
        from playbooks.meetings import Meeting

        # Initial state with no meetings
        execution_state.last_sent_state = execution_state.to_dict(full=True)

        # Add owned meeting
        meeting = Meeting("meeting_001", "1000", "TestAgent", "Planning session", [])
        execution_state.owned_meetings["meeting_001"] = meeting

        delta = execution_state.to_dict(full=False)

        assert delta is not None
        assert "owned_meetings" in delta
        assert len(delta["owned_meetings"]) > 0

    def test_delta_with_only_call_stack_change(self, execution_state):
        """Test delta when only call stack changes."""
        # Initial state
        step1 = PlaybookStep("01", "EXE", "Step 1", "- 01:EXE Step 1")
        ip1 = InstructionPointer("Playbook1", "01", 1, step1)
        frame1 = CallStackFrame(ip1)
        execution_state.call_stack.push(frame1)

        execution_state.last_sent_state = execution_state.to_dict(full=True)

        # Change call stack only
        step2 = PlaybookStep("02", "EXE", "Step 2", "- 02:EXE Step 2")
        ip2 = InstructionPointer("Playbook1", "02", 2, step2)
        frame2 = CallStackFrame(ip2)
        execution_state.call_stack.push(frame2)

        delta = execution_state.to_dict(full=False)

        assert delta is not None
        assert "call_stack" in delta
        # No variable changes
        assert "new_variables" not in delta
        assert "changed_variables" not in delta

    def test_delta_does_not_include_unchanged_meetings(self, execution_state):
        """Test that unchanged meetings are not included in delta."""
        from playbooks.meetings import Meeting

        # Setup initial meetings
        meeting = Meeting("meeting_001", "1000", "TestAgent", "Planning session", [])
        execution_state.owned_meetings["meeting_001"] = meeting

        execution_state.last_sent_state = execution_state.to_dict(full=True)

        # Change something else (add variable)
        execution_state.variables["$var1"] = "value1"

        delta = execution_state.to_dict(full=False)

        # Meetings shouldn't be in delta if unchanged
        assert delta is not None
        assert "owned_meetings" not in delta
        assert "new_variables" in delta

    def test_agents_list_copy_prevents_aliasing(self, execution_state):
        """Test that agents list is copied to prevent aliasing issues."""
        execution_state.agents = [{"id": "1001"}]

        state1 = execution_state.to_dict(full=True)

        # Modify original agents list
        execution_state.agents.append({"id": "1002"})

        # state1 should not be affected (it has a copy)
        assert len(state1["agents"]) == 1

        # Current state should have 2
        state2 = execution_state.to_dict(full=True)
        assert len(state2["agents"]) == 2


class TestInterpreterPromptIntegration:
    """Test suite for InterpreterPrompt integration with state compression."""

    def test_prompt_includes_state_block_for_full_state(self, execution_state):
        """Test that prompt includes state block for I-frames."""
        from playbooks.execution.interpreter_prompt import InterpreterPrompt

        execution_state.variables["$var1"] = "test_value"

        prompt_obj = InterpreterPrompt(
            execution_state=execution_state,
            playbooks={},
            current_playbook=None,
            instruction="Test instruction",
            agent_instructions="Test agent instructions",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="Test agent",
            other_agent_klasses_information=[],
            execution_id=1,
        )

        prompt = prompt_obj.prompt

        # Should include state block
        assert "*Current state*" in prompt
        assert "```json" in prompt
        assert '"variables"' in prompt
        assert '"$var1"' in prompt
        assert "test_value" in prompt

    def test_prompt_omits_state_block_for_empty_delta(self, execution_state):
        """Test that prompt omits state block for empty P-frames."""
        from playbooks.execution.interpreter_prompt import InterpreterPrompt

        # Set up initial state
        execution_state.variables["$var1"] = "test_value"
        execution_state.last_sent_state = execution_state.to_dict(full=True)
        execution_state.last_i_frame_execution_id = 1

        # Create prompt with no changes (P-frame with empty delta)
        prompt_obj = InterpreterPrompt(
            execution_state=execution_state,
            playbooks={},
            current_playbook=None,
            instruction="Test instruction",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="Test agent",
            other_agent_klasses_information=[],
            execution_id=2,
        )

        prompt = prompt_obj.prompt

        # Should NOT include state block
        assert "*Current state*" not in prompt
        assert '"variables"' not in prompt

    def test_prompt_includes_delta_state_with_changes(self, execution_state):
        """Test that prompt includes delta state for P-frames with changes."""
        from playbooks.execution.interpreter_prompt import InterpreterPrompt

        # Set up initial state
        execution_state.variables["$var1"] = "initial"
        execution_state.last_sent_state = execution_state.to_dict(full=True)
        execution_state.last_i_frame_execution_id = 1

        # Add a new variable
        execution_state.variables["$var2"] = "new_value"

        prompt_obj = InterpreterPrompt(
            execution_state=execution_state,
            playbooks={},
            current_playbook=None,
            instruction="Test instruction",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="Test agent",
            other_agent_klasses_information=[],
            execution_id=2,
        )

        prompt = prompt_obj.prompt

        # Should include delta state with "State changes" header
        assert "*State changes*" in prompt
        assert "new_variables" in prompt
        assert '"$var2"' in prompt
        assert "new_value" in prompt
        # Should NOT have old variable
        assert '"variables"' not in prompt  # Not full state

    def test_i_frame_type_propagates_to_message(self, execution_state):
        """Test that I-frame type is properly set on UserInputLLMMessage."""
        from playbooks.execution.interpreter_prompt import InterpreterPrompt
        from playbooks.llm.messages.types import FrameType

        # Ensure clean state for I-frame (first call scenario)
        execution_state.variables["$var1"] = "test"
        # Don't set last_sent_state - this ensures it's treated as first call

        prompt_obj = InterpreterPrompt(
            execution_state=execution_state,
            playbooks={},
            current_playbook=None,
            instruction="Test instruction",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="Test agent",
            other_agent_klasses_information=[],
            execution_id=1,
        )

        # Generate prompt (sets frame_type)
        _ = prompt_obj.prompt

        # Check that frame_type was set to I-frame
        assert prompt_obj.frame_type == FrameType.I

        # Generate messages (creates UserInputLLMMessage)
        prompt_obj.messages

        # Verify the message in call stack has correct frame_type
        if execution_state.call_stack.frames:
            user_messages = [
                msg
                for msg in execution_state.call_stack.frames[-1].llm_messages
                if hasattr(msg, "frame_type")
            ]
            if user_messages:
                assert user_messages[-1].frame_type == FrameType.I

    def test_p_frame_type_propagates_to_message(self, execution_state):
        """Test that P-frame type is properly set on UserInputLLMMessage."""
        from playbooks.execution.interpreter_prompt import InterpreterPrompt
        from playbooks.llm.messages.types import FrameType

        # Setup for P-frame (subsequent call with delta)
        execution_state.variables["$var1"] = "initial"
        execution_state.last_sent_state = execution_state.to_dict(full=True)
        execution_state.last_i_frame_execution_id = 1

        # Add new variable to create delta
        execution_state.variables["$var2"] = "new"

        prompt_obj = InterpreterPrompt(
            execution_state=execution_state,
            playbooks={},
            current_playbook=None,
            instruction="Test instruction",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="Test agent",
            other_agent_klasses_information=[],
            execution_id=2,
        )

        # Generate prompt (sets frame_type)
        _ = prompt_obj.prompt

        # Check that frame_type was set to P-frame
        assert prompt_obj.frame_type == FrameType.P

    def test_agent_instructions_included_for_i_frame(self, execution_state):
        """Test that agent instructions are included for I-frames."""
        from playbooks.execution.interpreter_prompt import InterpreterPrompt

        execution_state.variables["$var1"] = "test"

        prompt_obj = InterpreterPrompt(
            execution_state=execution_state,
            playbooks={},
            current_playbook=None,
            instruction="Test instruction",
            agent_instructions="Remember: You are TestAgent. Important context here.",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="Test agent",
            other_agent_klasses_information=[],
            execution_id=1,
        )

        prompt = prompt_obj.prompt

        # Agent instructions should be in I-frame
        assert "Remember: You are TestAgent" in prompt
        assert "Important context here" in prompt

    def test_agent_instructions_omitted_for_p_frame(self, execution_state):
        """Test that agent instructions are omitted for P-frames (token optimization)."""
        from playbooks.execution.interpreter_prompt import InterpreterPrompt

        # Setup for P-frame
        execution_state.variables["$var1"] = "initial"
        execution_state.last_sent_state = execution_state.to_dict(full=True)
        execution_state.last_i_frame_execution_id = 1

        # Add change to create delta
        execution_state.variables["$var2"] = "new"

        prompt_obj = InterpreterPrompt(
            execution_state=execution_state,
            playbooks={},
            current_playbook=None,
            instruction="Test instruction",
            agent_instructions="Remember: You are TestAgent. Important context here.",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="Test agent",
            other_agent_klasses_information=[],
            execution_id=2,
        )

        prompt = prompt_obj.prompt

        # Agent instructions should NOT be in P-frame (already in last I-frame)
        assert "Remember: You are TestAgent" not in prompt
        assert "Important context here" not in prompt


class TestCompactorIFrameBoundary:
    """Test suite for compactor I-frame boundary edge cases."""

    def test_i_frame_at_beginning_not_compacted(self):
        """Test that I-frame at beginning is preserved."""
        from playbooks.llm.llm_context_compactor import LLMContextCompactor
        from playbooks.llm.messages.types import (
            AssistantResponseLLMMessage,
            FrameType,
            UserInputLLMMessage,
        )

        messages = [
            UserInputLLMMessage(
                "I-frame", frame_type=FrameType.I
            ),  # Should be preserved
            AssistantResponseLLMMessage("response 1"),
            UserInputLLMMessage("message 2", frame_type=FrameType.P),
            AssistantResponseLLMMessage("response 2"),
        ]

        compactor = LLMContextCompactor()
        compacted = compactor.compact_messages(messages)

        # I-frame should be in output
        user_msgs = [m for m in compacted if m.get("role") == "user"]
        assert any("I-frame" in m.get("content", "") for m in user_msgs)

    def test_multiple_i_frames_only_preserves_last(self):
        """Test that only the last I-frame is preserved."""
        from playbooks.llm.llm_context_compactor import (
            CompactionConfig,
            LLMContextCompactor,
        )
        from playbooks.llm.messages.types import (
            AssistantResponseLLMMessage,
            FrameType,
            UserInputLLMMessage,
        )

        messages = [
            UserInputLLMMessage("I-frame 1", frame_type=FrameType.I),
            AssistantResponseLLMMessage("response 1"),
            UserInputLLMMessage(
                "I-frame 2", frame_type=FrameType.I
            ),  # Most recent I-frame
            AssistantResponseLLMMessage("response 2"),
            UserInputLLMMessage("P-frame", frame_type=FrameType.P),
            AssistantResponseLLMMessage("response 3"),
        ]

        # Use config that would normally compact first I-frame
        config = CompactionConfig(
            enabled=True, min_preserved_assistant_messages=1, batch_size=1
        )
        compactor = LLMContextCompactor(config)
        compacted = compactor.compact_messages(messages)

        # Last I-frame (I-frame 2) should be preserved
        user_msgs = [m for m in compacted if m.get("role") == "user"]
        has_i_frame_2 = any("I-frame 2" in m.get("content", "") for m in user_msgs)
        assert has_i_frame_2, "Last I-frame should be preserved"

    def test_compactor_with_only_i_frames(self):
        """Test compactor when all user messages are I-frames."""
        from playbooks.llm.llm_context_compactor import LLMContextCompactor
        from playbooks.llm.messages.types import (
            AssistantResponseLLMMessage,
            FrameType,
            UserInputLLMMessage,
        )

        messages = [
            UserInputLLMMessage("I-frame 1", frame_type=FrameType.I),
            AssistantResponseLLMMessage("response 1"),
            UserInputLLMMessage("I-frame 2", frame_type=FrameType.I),
            AssistantResponseLLMMessage("response 2"),
        ]

        compactor = LLMContextCompactor()
        compacted = compactor.compact_messages(messages)

        # Last I-frame should be preserved
        assert len(compacted) > 0
