"""Test checkpoint sorting to ensure numeric order, not alphabetic."""

import pytest
import tempfile
from pathlib import Path

from playbooks.checkpoints.filesystem import FilesystemCheckpointProvider


class TestCheckpointSorting:
    """Test that checkpoints are sorted by number, not alphabetically."""

    @pytest.mark.asyncio
    async def test_list_checkpoints_sorts_numerically(self):
        """Checkpoints should be sorted by number: 1, 2, 3, ..., 9, 10, 11.

        NOT alphabetically: 1, 10, 11, 2, 3, ...
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = FilesystemCheckpointProvider(base_path=tmpdir)

            # Create checkpoints in random order with numbers that would sort wrong alphabetically
            execution_id = "test_agent_1000"
            checkpoint_ids = [
                f"{execution_id}_ckpt_1",
                f"{execution_id}_ckpt_2",
                f"{execution_id}_ckpt_3",
                f"{execution_id}_ckpt_10",  # Would come after 1 alphabetically
                f"{execution_id}_ckpt_11",  # Would come after 1 alphabetically
                f"{execution_id}_ckpt_20",  # Would come after 2 alphabetically
            ]

            # Save checkpoints in random order
            for ckpt_id in [
                checkpoint_ids[3],
                checkpoint_ids[0],
                checkpoint_ids[5],
                checkpoint_ids[1],
                checkpoint_ids[4],
                checkpoint_ids[2],
            ]:
                await provider.save_checkpoint(
                    checkpoint_id=ckpt_id,
                    execution_state={"test": "state"},
                    namespace={},
                    metadata={"timestamp": 123},
                )

            # List checkpoints
            result = await provider.list_checkpoints(execution_id)

            # Should be sorted numerically
            expected = [
                f"{execution_id}_ckpt_1",
                f"{execution_id}_ckpt_2",
                f"{execution_id}_ckpt_3",
                f"{execution_id}_ckpt_10",
                f"{execution_id}_ckpt_11",
                f"{execution_id}_ckpt_20",
            ]

            assert result == expected, f"Expected numeric sort, got: {result}"

            # Verify latest is checkpoint 20, not 3 (which would be alphabetically last)
            assert result[-1] == f"{execution_id}_ckpt_20"

    @pytest.mark.asyncio
    async def test_list_checkpoints_latest_is_highest_number(self):
        """The last checkpoint in the list should be the highest numbered one."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = FilesystemCheckpointProvider(base_path=tmpdir)

            execution_id = "agent_1000"

            # Create checkpoints 1-9
            for i in range(1, 10):
                await provider.save_checkpoint(
                    checkpoint_id=f"{execution_id}_ckpt_{i}",
                    execution_state={"test": "state"},
                    namespace={},
                    metadata={"num": i},
                )

            result = await provider.list_checkpoints(execution_id)

            # Latest should be 9
            assert result[-1] == f"{execution_id}_ckpt_9"
            assert result[0] == f"{execution_id}_ckpt_1"

            # Should be in order 1, 2, 3, ..., 9
            expected = [f"{execution_id}_ckpt_{i}" for i in range(1, 10)]
            assert result == expected

    @pytest.mark.asyncio
    async def test_program_checkpoint_sorting(self):
        """Program checkpoints should also sort numerically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = FilesystemCheckpointProvider(base_path=tmpdir)

            session_id = "abc123-session"
            execution_id = f"{session_id}_program"

            # Create checkpoints that would sort wrong alphabetically
            checkpoint_nums = [1, 2, 9, 10, 11, 19, 20, 21, 100]

            for num in checkpoint_nums:
                await provider.save_checkpoint(
                    checkpoint_id=f"{execution_id}_ckpt_{num}",
                    execution_state={},
                    namespace={},
                    metadata={"checkpoint_counter": num},
                )

            result = await provider.list_checkpoints(execution_id)

            # Should be numerically sorted
            expected = [f"{execution_id}_ckpt_{num}" for num in sorted(checkpoint_nums)]
            assert result == expected

            # Latest should be 100
            assert result[-1] == f"{execution_id}_ckpt_100"

    @pytest.mark.asyncio
    async def test_empty_directory_returns_empty_list(self):
        """Non-existent execution should return empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = FilesystemCheckpointProvider(base_path=tmpdir)

            result = await provider.list_checkpoints("nonexistent_agent")

            assert result == []

    @pytest.mark.asyncio
    async def test_mixed_checkpoint_formats_ignored(self):
        """Only properly formatted checkpoints should be returned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = FilesystemCheckpointProvider(base_path=tmpdir)

            execution_id = "agent_1000"

            # Create valid checkpoints
            await provider.save_checkpoint(
                checkpoint_id=f"{execution_id}_ckpt_1",
                execution_state={"test": "state"},
                namespace={},
                metadata={},
            )
            await provider.save_checkpoint(
                checkpoint_id=f"{execution_id}_ckpt_2",
                execution_state={"test": "state"},
                namespace={},
                metadata={},
            )

            # Create invalid files manually
            exec_dir = Path(tmpdir) / execution_id
            exec_dir.mkdir(exist_ok=True)
            (exec_dir / "invalid.pkl").write_text("invalid")
            (exec_dir / "agent_1000.txt").write_text("not a checkpoint")

            result = await provider.list_checkpoints(execution_id)

            # Should only return valid checkpoints
            assert result == [f"{execution_id}_ckpt_1", f"{execution_id}_ckpt_2"]
