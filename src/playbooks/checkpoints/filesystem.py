"""Filesystem-based checkpoint storage for local development."""

import asyncio
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional

from playbooks.extensions import CheckpointProvider


class FilesystemCheckpointProvider(CheckpointProvider):
    """Filesystem-based checkpoint storage.

    Stores checkpoints as pickle files in a directory structure:
    .checkpoints/
        {execution_id}/
            ckpt_1.pkl
            ckpt_2.pkl
            ...

    Suitable for:
    - Development and testing
    - Single-node deployments
    - Local file system availability

    Limitations:
    - Single node only (no distributed coordination)
    - File system dependent
    - Limited to 10MB per checkpoint by default
    """

    def __init__(self, base_path: str = ".checkpoints", max_size_mb: int = 10):
        """Initialize filesystem checkpoint provider.

        Args:
            base_path: Base directory for checkpoint storage
            max_size_mb: Maximum checkpoint size in megabytes
        """
        self.base_path = Path(base_path)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_checkpoint_path(self, checkpoint_id: str) -> Path:
        """Get file path for a checkpoint ID.

        Args:
            checkpoint_id: Checkpoint identifier (format: execution_id_ckpt_N)

        Returns:
            Path to checkpoint file
        """
        execution_id = checkpoint_id.rsplit("_ckpt_", 1)[0]
        execution_dir = self.base_path / execution_id
        execution_dir.mkdir(parents=True, exist_ok=True)
        return execution_dir / f"{checkpoint_id}.pkl"

    def _get_execution_dir(self, execution_id: str) -> Path:
        """Get directory for an execution's checkpoints."""
        return self.base_path / execution_id

    async def save_checkpoint(
        self,
        checkpoint_id: str,
        execution_state: Dict[str, Any],
        namespace: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> None:
        """Save checkpoint to filesystem.

        Args:
            checkpoint_id: Unique checkpoint identifier
            execution_state: Serialized execution state
            namespace: Serialized namespace variables
            metadata: Additional metadata

        Raises:
            ValueError: If checkpoint exceeds size limit
        """
        checkpoint_data = {
            "checkpoint_id": checkpoint_id,
            "execution_state": execution_state,
            "namespace": namespace,
            "metadata": metadata,
        }

        serialized = pickle.dumps(checkpoint_data)

        if len(serialized) > self.max_size_bytes:
            size_mb = len(serialized) / (1024 * 1024)
            raise ValueError(
                f"Checkpoint {checkpoint_id} exceeds size limit: "
                f"{size_mb:.2f}MB > {self.max_size_bytes / (1024 * 1024)}MB"
            )

        checkpoint_path = self._get_checkpoint_path(checkpoint_id)

        await asyncio.to_thread(checkpoint_path.write_bytes, serialized)

    async def load_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Load checkpoint from filesystem.

        Args:
            checkpoint_id: Checkpoint identifier

        Returns:
            Checkpoint data or None if not found
        """
        checkpoint_path = self._get_checkpoint_path(checkpoint_id)

        if not await asyncio.to_thread(checkpoint_path.exists):
            return None

        data = await asyncio.to_thread(checkpoint_path.read_bytes)
        return pickle.loads(data)

    async def list_checkpoints(self, execution_id: str) -> List[str]:
        """List all checkpoints for an execution in chronological order.

        Args:
            execution_id: Execution identifier

        Returns:
            List of checkpoint IDs sorted by creation time
        """
        execution_dir = self._get_execution_dir(execution_id)

        if not execution_dir.exists():
            return []

        checkpoints = []
        for checkpoint_file in execution_dir.glob("*.pkl"):
            checkpoint_id = checkpoint_file.stem
            checkpoints.append((checkpoint_id, checkpoint_file.stat().st_mtime))

        checkpoints.sort(key=lambda x: x[1])
        return [checkpoint_id for checkpoint_id, _ in checkpoints]

    async def delete_checkpoint(self, checkpoint_id: str) -> None:
        """Delete a specific checkpoint.

        Args:
            checkpoint_id: Checkpoint identifier
        """
        checkpoint_path = self._get_checkpoint_path(checkpoint_id)

        if await asyncio.to_thread(checkpoint_path.exists):
            await asyncio.to_thread(checkpoint_path.unlink)

    async def cleanup_old_checkpoints(
        self, execution_id: str, keep_last_n: int = 10
    ) -> int:
        """Remove old checkpoints, keeping only the most recent ones.

        Args:
            execution_id: Execution identifier
            keep_last_n: Number of most recent checkpoints to keep

        Returns:
            Number of checkpoints deleted
        """
        checkpoints = await self.list_checkpoints(execution_id)

        if len(checkpoints) <= keep_last_n:
            return 0

        to_delete = checkpoints[:-keep_last_n]

        for checkpoint_id in to_delete:
            await self.delete_checkpoint(checkpoint_id)

        return len(to_delete)
