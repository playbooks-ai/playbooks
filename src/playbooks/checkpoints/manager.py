"""Checkpoint manager for coordinating checkpoint operations."""

import logging
import time
from typing import Any, Dict, Optional

from playbooks.extensions import CheckpointProvider

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages checkpoint lifecycle and coordination.

    Provides high-level interface for saving/loading checkpoints and coordinates
    with the underlying storage provider.
    """

    def __init__(self, execution_id: str, provider: CheckpointProvider):
        """Initialize checkpoint manager.

        Args:
            execution_id: Unique execution identifier (typically agent_id)
            provider: Checkpoint storage provider
        """
        self.execution_id = execution_id
        self.provider = provider
        self.checkpoint_counter = 0

    async def save_checkpoint(
        self,
        statement_code: str,
        namespace: Dict[str, Any],
        execution_state: Dict[str, Any],
        call_stack: list,
        llm_response: Optional[str] = None,
        executed_code: Optional[str] = None,
    ) -> str:
        """Save a checkpoint after statement execution.

        Args:
            statement_code: The code statement that was executed
            namespace: Current namespace state
            execution_state: Serialized execution state
            call_stack: Current call stack
            llm_response: Full LLM response being executed (for resume)
            executed_code: Code already executed from LLM response (for resume)

        Returns:
            Checkpoint ID
        """
        self.checkpoint_counter += 1
        checkpoint_id = f"{self.execution_id}_ckpt_{self.checkpoint_counter}"

        metadata = {
            "statement": statement_code,
            "counter": self.checkpoint_counter,
            "execution_id": self.execution_id,
            "timestamp": time.time(),
            "call_stack": call_stack,
            "llm_response": llm_response,
            "executed_code": executed_code,
        }

        serializable_namespace = self._prepare_namespace(namespace)

        await self.provider.save_checkpoint(
            checkpoint_id=checkpoint_id,
            execution_state=execution_state,
            namespace=serializable_namespace,
            metadata=metadata,
        )

        logger.debug(
            f"Checkpoint saved: {checkpoint_id} "
            f"(statement: {statement_code[:50]}...)"
        )

        return checkpoint_id

    async def load_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Load a checkpoint.

        Args:
            checkpoint_id: Checkpoint identifier

        Returns:
            Checkpoint data or None if not found
        """
        return await self.provider.load_checkpoint(checkpoint_id)

    async def get_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Get the most recent checkpoint for this execution.

        Returns:
            Latest checkpoint data or None if no checkpoints exist
        """
        checkpoints = await self.provider.list_checkpoints(self.execution_id)

        if not checkpoints:
            return None

        latest_checkpoint_id = checkpoints[-1]
        return await self.load_checkpoint(latest_checkpoint_id)

    async def cleanup_old_checkpoints(self, keep_last_n: int = 10) -> int:
        """Remove old checkpoints to manage storage.

        Args:
            keep_last_n: Number of most recent checkpoints to keep

        Returns:
            Number of checkpoints deleted
        """
        return await self.provider.cleanup_old_checkpoints(
            self.execution_id, keep_last_n
        )

    def _prepare_namespace(self, namespace: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare namespace for serialization.

        Filters out non-serializable items like functions, modules, and builtins.
        Keeps: primitives, collections, classes, instances
        Filters: functions, modules, built-in objects

        Args:
            namespace: Raw namespace dict

        Returns:
            Filtered namespace dict with only serializable values
        """
        import pickle

        serializable = {}

        for key, value in namespace.items():
            if key.startswith("_"):
                continue

            if key in ("asyncio",):
                continue

            if callable(value):
                if isinstance(value, type):
                    pass
                else:
                    continue

            try:
                pickle.dumps(value)
                serializable[key] = value
            except Exception as e:
                logger.debug(f"Skipping non-serializable variable {key}: {e}")

        return serializable
