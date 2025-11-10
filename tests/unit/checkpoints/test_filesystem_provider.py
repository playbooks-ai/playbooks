"""Tests for filesystem checkpoint provider."""

import pytest
import tempfile

from playbooks.checkpoints.filesystem import FilesystemCheckpointProvider


class TestFilesystemCheckpointProvider:
    """Test suite for FilesystemCheckpointProvider."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for checkpoints."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def provider(self, temp_dir):
        """Create provider instance."""
        return FilesystemCheckpointProvider(base_path=temp_dir)

    @pytest.mark.asyncio
    async def test_save_and_load_checkpoint(self, provider):
        """Test basic save and load cycle."""
        checkpoint_id = "test_execution_ckpt_1"
        execution_state = {"variables": {"x": 10, "y": 20}}
        namespace = {"x": 10, "y": 20, "result": 30}
        metadata = {"timestamp": 123456.789, "statement": "result = x + y"}

        await provider.save_checkpoint(
            checkpoint_id=checkpoint_id,
            execution_state=execution_state,
            namespace=namespace,
            metadata=metadata,
        )

        loaded = await provider.load_checkpoint(checkpoint_id)

        assert loaded is not None
        assert loaded["checkpoint_id"] == checkpoint_id
        assert loaded["execution_state"] == execution_state
        assert loaded["namespace"] == namespace
        assert loaded["metadata"] == metadata

    @pytest.mark.asyncio
    async def test_load_nonexistent_checkpoint(self, provider):
        """Test loading checkpoint that doesn't exist."""
        loaded = await provider.load_checkpoint("nonexistent_ckpt_1")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_list_checkpoints_empty(self, provider):
        """Test listing checkpoints when none exist."""
        checkpoints = await provider.list_checkpoints("test_execution")
        assert checkpoints == []

    @pytest.mark.asyncio
    async def test_list_checkpoints_multiple(self, provider):
        """Test listing multiple checkpoints in order."""
        execution_id = "test_execution"

        for i in range(1, 4):
            checkpoint_id = f"{execution_id}_ckpt_{i}"
            await provider.save_checkpoint(
                checkpoint_id=checkpoint_id,
                execution_state={},
                namespace={},
                metadata={"counter": i},
            )

        checkpoints = await provider.list_checkpoints(execution_id)

        assert len(checkpoints) == 3
        assert checkpoints[0] == f"{execution_id}_ckpt_1"
        assert checkpoints[1] == f"{execution_id}_ckpt_2"
        assert checkpoints[2] == f"{execution_id}_ckpt_3"

    @pytest.mark.asyncio
    async def test_delete_checkpoint(self, provider):
        """Test checkpoint deletion."""
        checkpoint_id = "test_execution_ckpt_1"

        await provider.save_checkpoint(
            checkpoint_id=checkpoint_id, execution_state={}, namespace={}, metadata={}
        )

        loaded = await provider.load_checkpoint(checkpoint_id)
        assert loaded is not None

        await provider.delete_checkpoint(checkpoint_id)

        loaded = await provider.load_checkpoint(checkpoint_id)
        assert loaded is None

    @pytest.mark.asyncio
    async def test_cleanup_old_checkpoints(self, provider):
        """Test cleanup of old checkpoints."""
        execution_id = "test_execution"

        for i in range(1, 16):
            checkpoint_id = f"{execution_id}_ckpt_{i}"
            await provider.save_checkpoint(
                checkpoint_id=checkpoint_id,
                execution_state={},
                namespace={},
                metadata={},
            )

        checkpoints = await provider.list_checkpoints(execution_id)
        assert len(checkpoints) == 15

        deleted_count = await provider.cleanup_old_checkpoints(
            execution_id, keep_last_n=10
        )

        assert deleted_count == 5

        checkpoints = await provider.list_checkpoints(execution_id)
        assert len(checkpoints) == 10
        assert checkpoints[0] == f"{execution_id}_ckpt_6"
        assert checkpoints[-1] == f"{execution_id}_ckpt_15"

    @pytest.mark.asyncio
    async def test_cleanup_with_fewer_checkpoints_than_keep(self, provider):
        """Test cleanup when there are fewer checkpoints than keep_last_n."""
        execution_id = "test_execution"

        for i in range(1, 4):
            checkpoint_id = f"{execution_id}_ckpt_{i}"
            await provider.save_checkpoint(
                checkpoint_id=checkpoint_id,
                execution_state={},
                namespace={},
                metadata={},
            )

        deleted_count = await provider.cleanup_old_checkpoints(
            execution_id, keep_last_n=10
        )

        assert deleted_count == 0

        checkpoints = await provider.list_checkpoints(execution_id)
        assert len(checkpoints) == 3

    @pytest.mark.asyncio
    async def test_checkpoint_size_limit(self, provider):
        """Test that checkpoint size limit is enforced."""
        large_namespace = {f"var_{i}": "x" * 10000 for i in range(2000)}

        with pytest.raises(ValueError, match="exceeds size limit"):
            await provider.save_checkpoint(
                checkpoint_id="test_execution_ckpt_1",
                execution_state={},
                namespace=large_namespace,
                metadata={},
            )

    @pytest.mark.asyncio
    async def test_multiple_executions_isolated(self, provider):
        """Test that checkpoints from different executions are isolated."""
        execution_1 = "execution_1"
        execution_2 = "execution_2"

        await provider.save_checkpoint(
            checkpoint_id=f"{execution_1}_ckpt_1",
            execution_state={},
            namespace={},
            metadata={},
        )

        await provider.save_checkpoint(
            checkpoint_id=f"{execution_2}_ckpt_1",
            execution_state={},
            namespace={},
            metadata={},
        )

        checkpoints_1 = await provider.list_checkpoints(execution_1)
        checkpoints_2 = await provider.list_checkpoints(execution_2)

        assert len(checkpoints_1) == 1
        assert len(checkpoints_2) == 1
        assert checkpoints_1[0] == f"{execution_1}_ckpt_1"
        assert checkpoints_2[0] == f"{execution_2}_ckpt_1"
