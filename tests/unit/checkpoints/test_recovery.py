"""Tests for recovery coordinator."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from playbooks.checkpoints.recovery import RecoveryCoordinator
from playbooks.checkpoints.manager import CheckpointManager


class TestRecoveryCoordinator:
    """Test suite for RecoveryCoordinator."""

    @pytest.fixture
    def mock_checkpoint_manager(self):
        """Create mock checkpoint manager."""
        manager = MagicMock(spec=CheckpointManager)
        manager.execution_id = "test_agent_123"
        manager.get_latest_checkpoint = AsyncMock()
        return manager

    @pytest.fixture
    def recovery_coordinator(self, mock_checkpoint_manager):
        """Create recovery coordinator instance."""
        return RecoveryCoordinator(mock_checkpoint_manager)

    @pytest.mark.asyncio
    async def test_can_recover_when_checkpoints_exist(
        self, recovery_coordinator, mock_checkpoint_manager
    ):
        """Test that can_recover returns True when checkpoints exist."""
        mock_checkpoint_manager.get_latest_checkpoint.return_value = {
            "checkpoint_id": "test_agent_123_ckpt_1",
            "execution_state": {},
            "namespace": {},
            "metadata": {},
        }

        result = await recovery_coordinator.can_recover()

        assert result is True

    @pytest.mark.asyncio
    async def test_can_recover_when_no_checkpoints(
        self, recovery_coordinator, mock_checkpoint_manager
    ):
        """Test that can_recover returns False when no checkpoints."""
        mock_checkpoint_manager.get_latest_checkpoint.return_value = None

        result = await recovery_coordinator.can_recover()

        assert result is False

    @pytest.mark.asyncio
    async def test_get_recovery_info(
        self, recovery_coordinator, mock_checkpoint_manager
    ):
        """Test getting recovery information."""
        mock_checkpoint_manager.get_latest_checkpoint.return_value = {
            "checkpoint_id": "test_agent_123_ckpt_5",
            "execution_state": {},
            "namespace": {},
            "metadata": {
                "statement": "await Say('user', 'Hello')",
                "counter": 5,
                "timestamp": 1234567.89,
            },
        }

        info = await recovery_coordinator.get_recovery_info()

        assert info is not None
        assert info["checkpoint_id"] == "test_agent_123_ckpt_5"
        assert info["statement"] == "await Say('user', 'Hello')"
        assert info["counter"] == 5
        assert info["timestamp"] == 1234567.89

    @pytest.mark.asyncio
    async def test_get_recovery_info_when_no_checkpoints(
        self, recovery_coordinator, mock_checkpoint_manager
    ):
        """Test get_recovery_info returns None when no checkpoints."""
        mock_checkpoint_manager.get_latest_checkpoint.return_value = None

        info = await recovery_coordinator.get_recovery_info()

        assert info is None

    @pytest.mark.asyncio
    async def test_recover_execution_state(
        self, recovery_coordinator, mock_checkpoint_manager
    ):
        """Test recovering execution state."""
        mock_agent = MagicMock()
        mock_agent.state.variables = {}
        mock_agent.state.agents = []

        mock_checkpoint_manager.get_latest_checkpoint.return_value = {
            "checkpoint_id": "test_agent_123_ckpt_3",
            "execution_state": {
                "variables": {"$x": 10, "$y": 20},
                "agents": ["agent1", "agent2"],
            },
            "namespace": {"x": 10, "y": 20, "result": 30},
            "metadata": {
                "statement": "result = x + y",
                "counter": 3,
                "timestamp": 1234567.89,
            },
        }

        recovered = await recovery_coordinator.recover_execution_state(mock_agent)

        assert recovered["checkpoint_id"] == "test_agent_123_ckpt_3"
        assert recovered["namespace"] == {"x": 10, "y": 20, "result": 30}
        assert recovered["metadata"]["statement"] == "result = x + y"

        assert mock_agent.state.variables["$x"] == 10
        assert mock_agent.state.variables["$y"] == 20
        assert mock_agent.state.agents == ["agent1", "agent2"]

    @pytest.mark.asyncio
    async def test_recover_execution_state_raises_when_no_checkpoints(
        self, recovery_coordinator, mock_checkpoint_manager
    ):
        """Test that recovery raises error when no checkpoints."""
        mock_agent = MagicMock()
        mock_checkpoint_manager.get_latest_checkpoint.return_value = None

        with pytest.raises(ValueError, match="No checkpoints available"):
            await recovery_coordinator.recover_execution_state(mock_agent)
