"""Extension points for pluggable functionality.

This module defines abstract interfaces that external packages can implement
to extend playbooks functionality. The baseline implementation is in the core
package, and enterprise packages can provide enhanced implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class CheckpointProvider(ABC):
    """Abstract interface for execution checkpointing.

    The core package provides a filesystem-based implementation suitable for
    development and single-node deployments. Enterprise packages can provide
    scalable implementations with PostgreSQL, Redis, or distributed storage.
    """

    @abstractmethod
    async def save_checkpoint(
        self,
        checkpoint_id: str,
        execution_state: Dict[str, Any],
        namespace: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> None:
        """Save execution checkpoint.

        Args:
            checkpoint_id: Unique checkpoint identifier
            execution_state: Serialized execution state
            namespace: Serialized namespace variables
            metadata: Additional metadata (timestamp, agent_id, statement, etc.)
        """
        pass

    @abstractmethod
    async def load_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Load checkpoint data.

        Args:
            checkpoint_id: Checkpoint identifier

        Returns:
            Checkpoint data dict or None if not found
        """
        pass

    @abstractmethod
    async def list_checkpoints(self, execution_id: str) -> List[str]:
        """List all checkpoint IDs for an execution.

        Args:
            execution_id: Execution identifier (typically agent_id)

        Returns:
            List of checkpoint IDs in chronological order
        """
        pass

    @abstractmethod
    async def delete_checkpoint(self, checkpoint_id: str) -> None:
        """Delete a specific checkpoint.

        Args:
            checkpoint_id: Checkpoint identifier
        """
        pass

    @abstractmethod
    async def cleanup_old_checkpoints(
        self, execution_id: str, keep_last_n: int = 10
    ) -> int:
        """Remove old checkpoints to manage storage.

        Args:
            execution_id: Execution identifier
            keep_last_n: Number of most recent checkpoints to keep

        Returns:
            Number of checkpoints deleted
        """
        pass


__all__ = ["CheckpointProvider"]
