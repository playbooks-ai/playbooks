"""Tests for checkpoint manager."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from playbooks.checkpoints.manager import CheckpointManager


class TestCheckpointManager:
    """Test suite for CheckpointManager."""

    @pytest.fixture
    def mock_provider(self):
        """Create mock checkpoint provider."""
        provider = MagicMock()
        provider.save_checkpoint = AsyncMock()
        provider.load_checkpoint = AsyncMock(return_value=None)
        provider.list_checkpoints = AsyncMock(return_value=[])
        provider.cleanup_old_checkpoints = AsyncMock(return_value=0)
        return provider

    @pytest.fixture
    def manager(self, mock_provider):
        """Create checkpoint manager instance."""
        return CheckpointManager(execution_id="test_agent_123", provider=mock_provider)

    @pytest.mark.asyncio
    async def test_save_checkpoint(self, manager, mock_provider):
        """Test saving a checkpoint."""
        namespace = {"x": 10, "y": 20, "result": 30}
        execution_state = {"variables": {"$x": 10, "$y": 20}}
        call_stack = ["Main:01"]

        checkpoint_id = await manager.save_checkpoint(
            statement_code="result = x + y",
            namespace=namespace,
            execution_state=execution_state,
            call_stack=call_stack,
        )

        assert checkpoint_id == "test_agent_123_ckpt_1"
        assert manager.checkpoint_counter == 1

        mock_provider.save_checkpoint.assert_called_once()
        call_args = mock_provider.save_checkpoint.call_args

        assert call_args.kwargs["checkpoint_id"] == checkpoint_id
        assert call_args.kwargs["execution_state"] == execution_state
        assert "x" in call_args.kwargs["namespace"]
        assert call_args.kwargs["metadata"]["statement"] == "result = x + y"
        assert call_args.kwargs["metadata"]["counter"] == 1

    @pytest.mark.asyncio
    async def test_save_multiple_checkpoints_increments_counter(
        self, manager, mock_provider
    ):
        """Test that checkpoint counter increments correctly."""
        for i in range(3):
            checkpoint_id = await manager.save_checkpoint(
                statement_code=f"statement_{i}",
                namespace={},
                execution_state={},
                call_stack=[],
            )
            assert checkpoint_id == f"test_agent_123_ckpt_{i + 1}"

        assert manager.checkpoint_counter == 3
        assert mock_provider.save_checkpoint.call_count == 3

    @pytest.mark.asyncio
    async def test_load_checkpoint(self, manager, mock_provider):
        """Test loading a checkpoint."""
        mock_provider.load_checkpoint.return_value = {
            "checkpoint_id": "test_agent_123_ckpt_1",
            "execution_state": {},
            "namespace": {},
            "metadata": {},
        }

        checkpoint = await manager.load_checkpoint("test_agent_123_ckpt_1")

        assert checkpoint is not None
        assert checkpoint["checkpoint_id"] == "test_agent_123_ckpt_1"
        mock_provider.load_checkpoint.assert_called_once_with("test_agent_123_ckpt_1")

    @pytest.mark.asyncio
    async def test_get_latest_checkpoint(self, manager, mock_provider):
        """Test getting the latest checkpoint."""
        mock_provider.list_checkpoints.return_value = [
            "test_agent_123_ckpt_1",
            "test_agent_123_ckpt_2",
            "test_agent_123_ckpt_3",
        ]

        mock_provider.load_checkpoint.return_value = {
            "checkpoint_id": "test_agent_123_ckpt_3",
            "metadata": {"counter": 3},
        }

        latest = await manager.get_latest_checkpoint()

        assert latest is not None
        assert latest["checkpoint_id"] == "test_agent_123_ckpt_3"
        mock_provider.list_checkpoints.assert_called_once_with("test_agent_123")
        mock_provider.load_checkpoint.assert_called_once_with("test_agent_123_ckpt_3")

    @pytest.mark.asyncio
    async def test_get_latest_checkpoint_when_none_exist(self, manager, mock_provider):
        """Test getting latest checkpoint when no checkpoints exist."""
        mock_provider.list_checkpoints.return_value = []

        latest = await manager.get_latest_checkpoint()

        assert latest is None
        mock_provider.list_checkpoints.assert_called_once_with("test_agent_123")
        mock_provider.load_checkpoint.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_old_checkpoints(self, manager, mock_provider):
        """Test cleanup of old checkpoints."""
        mock_provider.cleanup_old_checkpoints.return_value = 5

        deleted_count = await manager.cleanup_old_checkpoints(keep_last_n=10)

        assert deleted_count == 5
        mock_provider.cleanup_old_checkpoints.assert_called_once_with(
            "test_agent_123", 10
        )

    @pytest.mark.asyncio
    async def test_prepare_namespace_filters_functions(self, manager):
        """Test that namespace preparation filters out functions."""

        def my_function():
            pass

        namespace = {"x": 10, "y": 20, "my_func": my_function, "result": 30}

        prepared = manager._prepare_namespace(namespace)

        assert "x" in prepared
        assert "y" in prepared
        assert "result" in prepared
        assert "my_func" not in prepared

    @pytest.mark.asyncio
    async def test_prepare_namespace_filters_private_vars(self, manager):
        """Test that namespace preparation filters out private variables."""
        namespace = {"x": 10, "_private": 20, "__dunder__": 30, "result": 40}

        prepared = manager._prepare_namespace(namespace)

        assert "x" in prepared
        assert "result" in prepared
        assert "_private" not in prepared
        assert "__dunder__" not in prepared

    @pytest.mark.asyncio
    async def test_prepare_namespace_filters_asyncio(self, manager):
        """Test that namespace preparation filters out asyncio module."""
        import asyncio

        namespace = {"x": 10, "asyncio": asyncio, "result": 20}

        prepared = manager._prepare_namespace(namespace)

        assert "x" in prepared
        assert "result" in prepared
        assert "asyncio" not in prepared

    @pytest.mark.asyncio
    async def test_prepare_namespace_handles_unpicklable_classes(self, manager):
        """Test that locally-defined classes are filtered out (pickle limitation)."""

        class LocalClass:
            pass

        namespace = {"x": 10, "LocalClass": LocalClass, "result": 20}

        prepared = manager._prepare_namespace(namespace)

        assert "x" in prepared
        assert "result" in prepared
        assert "LocalClass" not in prepared

    @pytest.mark.asyncio
    async def test_prepare_namespace_keeps_module_level_types(self, manager):
        """Test that module-level types are kept."""
        namespace = {"x": 10, "list": list, "dict": dict, "result": 20}

        prepared = manager._prepare_namespace(namespace)

        assert "x" in prepared
        assert "result" in prepared
        assert "list" in prepared
        assert "dict" in prepared
