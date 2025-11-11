"""Test call stack restoration from checkpoints."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from playbooks.checkpoints.recovery import RecoveryCoordinator
from playbooks.checkpoints.manager import CheckpointManager
from playbooks.state.call_stack import CallStack, CallStackFrame, InstructionPointer


class TestCallStackRestoration:
    """Test that call stacks are properly restored from checkpoints."""

    @pytest.mark.asyncio
    async def test_call_stack_restored_from_checkpoint(self):
        """Call stack should be restored from checkpoint metadata."""
        # Create mock agent with call stack
        mock_agent = MagicMock()
        mock_agent.state = MagicMock()
        mock_agent.state.variables = {}
        mock_agent.state.agents = []
        mock_agent.state.call_stack = CallStack(
            event_bus=MagicMock(), agent_id="test_agent"
        )

        # Create mock checkpoint manager
        mock_provider = AsyncMock()
        manager = CheckpointManager(execution_id="test_agent", provider=mock_provider)

        # Mock checkpoint data with call stack
        checkpoint_data = {
            "checkpoint_id": "test_agent_ckpt_1",
            "execution_state": {"variables": {"x": 10}, "agents": []},
            "namespace": {"x": 10},
            "metadata": {
                "statement": "await Step('Main:03:QUE')",
                "counter": 1,
                "timestamp": 123456,
                "call_stack": [
                    {"playbook": "Main", "line_number": "01", "source_line_number": 5},
                    {"playbook": "Main", "line_number": "03", "source_line_number": 10},
                ],
            },
        }

        # Mock get_latest_checkpoint to return our test data
        manager.get_latest_checkpoint = AsyncMock(return_value=checkpoint_data)

        # Create recovery coordinator
        coordinator = RecoveryCoordinator(manager)

        # Restore execution state
        await coordinator.recover_execution_state(mock_agent)

        # Verify call stack was restored
        assert len(mock_agent.state.call_stack.frames) == 2

        # Check first frame
        frame1 = mock_agent.state.call_stack.frames[0]
        assert frame1.instruction_pointer.playbook == "Main"
        assert frame1.instruction_pointer.line_number == "01"
        assert frame1.instruction_pointer.source_line_number == 5

        # Check second frame
        frame2 = mock_agent.state.call_stack.frames[1]
        assert frame2.instruction_pointer.playbook == "Main"
        assert frame2.instruction_pointer.line_number == "03"
        assert frame2.instruction_pointer.source_line_number == 10

    @pytest.mark.asyncio
    async def test_empty_call_stack_handled(self):
        """Empty call stack should not cause errors."""
        mock_agent = MagicMock()
        mock_agent.state = MagicMock()
        mock_agent.state.variables = {}
        mock_agent.state.agents = []
        mock_agent.state.call_stack = CallStack(
            event_bus=MagicMock(), agent_id="test_agent"
        )

        mock_provider = AsyncMock()
        manager = CheckpointManager(execution_id="test_agent", provider=mock_provider)

        # Checkpoint with empty call stack
        checkpoint_data = {
            "checkpoint_id": "test_agent_ckpt_1",
            "execution_state": {"variables": {}, "agents": []},
            "namespace": {},
            "metadata": {
                "statement": "await Step('Main:01:SEQ')",
                "counter": 1,
                "timestamp": 123456,
                "call_stack": [],  # Empty
            },
        }

        manager.get_latest_checkpoint = AsyncMock(return_value=checkpoint_data)
        coordinator = RecoveryCoordinator(manager)

        # Should not raise
        await coordinator.recover_execution_state(mock_agent)

        # Call stack should be empty
        assert len(mock_agent.state.call_stack.frames) == 0

    @pytest.mark.asyncio
    async def test_call_stack_clears_before_restore(self):
        """Existing call stack should be cleared before restoring."""
        mock_agent = MagicMock()
        mock_agent.state = MagicMock()
        mock_agent.state.variables = {}
        mock_agent.state.agents = []
        mock_agent.state.call_stack = CallStack(
            event_bus=MagicMock(), agent_id="test_agent"
        )

        # Add some existing frames
        ip1 = InstructionPointer("OldPlaybook", "99", 999)
        mock_agent.state.call_stack.frames.append(CallStackFrame(ip1))

        assert len(mock_agent.state.call_stack.frames) == 1

        mock_provider = AsyncMock()
        manager = CheckpointManager(execution_id="test_agent", provider=mock_provider)

        # Checkpoint with new call stack
        checkpoint_data = {
            "checkpoint_id": "test_agent_ckpt_1",
            "execution_state": {"variables": {}, "agents": []},
            "namespace": {},
            "metadata": {
                "statement": "await Step('Main:01:SEQ')",
                "counter": 1,
                "timestamp": 123456,
                "call_stack": [
                    {
                        "playbook": "NewPlaybook",
                        "line_number": "01",
                        "source_line_number": 5,
                    }
                ],
            },
        }

        manager.get_latest_checkpoint = AsyncMock(return_value=checkpoint_data)
        coordinator = RecoveryCoordinator(manager)

        await coordinator.recover_execution_state(mock_agent)

        # Should have only the restored frame, not the old one
        assert len(mock_agent.state.call_stack.frames) == 1
        assert (
            mock_agent.state.call_stack.frames[0].instruction_pointer.playbook
            == "NewPlaybook"
        )
        assert (
            mock_agent.state.call_stack.frames[0].instruction_pointer.line_number
            == "01"
        )

    @pytest.mark.asyncio
    async def test_nested_call_stack_preserved(self):
        """Nested call stacks (from playbook calls) should be preserved."""
        mock_agent = MagicMock()
        mock_agent.state = MagicMock()
        mock_agent.state.variables = {}
        mock_agent.state.agents = []
        mock_agent.state.call_stack = CallStack(
            event_bus=MagicMock(), agent_id="test_agent"
        )

        mock_provider = AsyncMock()
        manager = CheckpointManager(execution_id="test_agent", provider=mock_provider)

        # Checkpoint with nested call stack (3 levels deep)
        checkpoint_data = {
            "checkpoint_id": "test_agent_ckpt_1",
            "execution_state": {"variables": {}, "agents": []},
            "namespace": {},
            "metadata": {
                "statement": "await Step('Helper:02:SEQ')",
                "counter": 1,
                "timestamp": 123456,
                "call_stack": [
                    {"playbook": "Main", "line_number": "01", "source_line_number": 5},
                    {
                        "playbook": "SubTask",
                        "line_number": "03",
                        "source_line_number": 15,
                    },
                    {
                        "playbook": "Helper",
                        "line_number": "02",
                        "source_line_number": 25,
                    },
                ],
            },
        }

        manager.get_latest_checkpoint = AsyncMock(return_value=checkpoint_data)
        coordinator = RecoveryCoordinator(manager)

        await coordinator.recover_execution_state(mock_agent)

        # Verify all 3 frames restored
        assert len(mock_agent.state.call_stack.frames) == 3
        assert mock_agent.state.call_stack.frames[0].playbook == "Main"
        assert mock_agent.state.call_stack.frames[1].playbook == "SubTask"
        assert mock_agent.state.call_stack.frames[2].playbook == "Helper"

        # Verify depths are set correctly
        assert mock_agent.state.call_stack.frames[0].depth == 1
        assert mock_agent.state.call_stack.frames[1].depth == 2
        assert mock_agent.state.call_stack.frames[2].depth == 3
