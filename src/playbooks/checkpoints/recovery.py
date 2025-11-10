"""Recovery coordinator for resuming execution from checkpoints."""

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from playbooks.agents.local_ai_agent import LocalAIAgent

from .manager import CheckpointManager

logger = logging.getLogger(__name__)


class RecoveryCoordinator:
    """Coordinates recovery of interrupted playbook executions.

    Handles loading checkpoints and restoring execution state to resume
    from the point of failure.
    """

    def __init__(self, checkpoint_manager: CheckpointManager):
        """Initialize recovery coordinator.

        Args:
            checkpoint_manager: Checkpoint manager for the execution
        """
        self.checkpoint_manager = checkpoint_manager

    async def can_recover(self) -> bool:
        """Check if recovery is possible for this execution.

        Returns:
            True if checkpoints exist for recovery
        """
        latest = await self.checkpoint_manager.get_latest_checkpoint()
        return latest is not None

    async def get_recovery_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the recovery point.

        Returns:
            Dictionary with checkpoint metadata or None if no checkpoints
        """
        latest = await self.checkpoint_manager.get_latest_checkpoint()
        if latest:
            return {
                "checkpoint_id": latest["checkpoint_id"],
                "statement": latest["metadata"]["statement"],
                "counter": latest["metadata"]["counter"],
                "timestamp": latest["metadata"]["timestamp"],
            }
        return None

    async def recover_execution_state(self, agent: "LocalAIAgent") -> Dict[str, Any]:
        """Recover execution state from latest checkpoint.

        Restores agent state including variables, call stack, and namespace
        from the most recent checkpoint.

        Args:
            agent: Agent to restore state into

        Returns:
            Dictionary containing recovered state components

        Raises:
            ValueError: If no checkpoints available for recovery
        """
        latest_checkpoint = await self.checkpoint_manager.get_latest_checkpoint()

        if not latest_checkpoint:
            raise ValueError(
                f"No checkpoints available for execution "
                f"{self.checkpoint_manager.execution_id}"
            )

        checkpoint_id = latest_checkpoint["checkpoint_id"]
        logger.info(f"Recovering from checkpoint: {checkpoint_id}")

        execution_state = latest_checkpoint["execution_state"]
        namespace = latest_checkpoint["namespace"]
        metadata = latest_checkpoint["metadata"]

        self._restore_execution_state(agent, execution_state)

        logger.info(
            f"Recovery complete from checkpoint {checkpoint_id} "
            f"(statement: {metadata['statement'][:50]}...)"
        )

        return {
            "checkpoint_id": checkpoint_id,
            "namespace": namespace,
            "metadata": metadata,
            "execution_state": execution_state,
        }

    def _restore_execution_state(
        self, agent: "LocalAIAgent", state_dict: Dict[str, Any]
    ) -> None:
        """Restore agent execution state from checkpoint data.

        Args:
            agent: Agent to restore state into
            state_dict: Serialized execution state from checkpoint
        """
        for var_name, var_value in state_dict.get("variables", {}).items():
            agent.state.variables[var_name] = var_value

        if "agents" in state_dict:
            agent.state.agents = state_dict["agents"]
