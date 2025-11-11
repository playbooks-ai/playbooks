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

        # Restore execution state AND call stack
        self._restore_execution_state(agent, execution_state)
        self._restore_call_stack(agent, metadata.get("call_stack", []))

        # Mark agent as restored so it doesn't call begin() again
        agent.restored_from_checkpoint = True

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

    def _restore_call_stack(self, agent: "LocalAIAgent", call_stack_data: list) -> None:
        """Restore call stack from checkpoint data.

        Args:
            agent: Agent to restore call stack into
            call_stack_data: List of call stack frame dicts from checkpoint
        """
        from playbooks.state.call_stack import CallStackFrame, InstructionPointer
        from playbooks.utils.langfuse_helper import LangfuseHelper

        # Clear existing call stack
        agent.state.call_stack.frames.clear()

        # Restore each frame from the checkpoint
        for frame_dict in call_stack_data:
            # Handle both old format (just IP dict) and new format (full frame dict)
            if "instruction_pointer" in frame_dict:
                # New format: full frame serialization
                ip_str = frame_dict["instruction_pointer"]
                # Parse "Playbook:line_number" format
                if ":" in ip_str:
                    parts = ip_str.rsplit(":", 1)
                    playbook = parts[0]
                    line_number = parts[1] if len(parts) > 1 else None
                else:
                    playbook = ip_str
                    line_number = None

                instruction_pointer = InstructionPointer(
                    playbook=playbook,
                    line_number=line_number,
                    source_line_number=0,  # We don't have this in string format
                )

                # Try to create langfuse span for resumed execution
                langfuse_span = None
                langfuse_info = frame_dict.get("langfuse_info")
                if langfuse_info and langfuse_info.get("type") == "langfuse_span":
                    # Create a new span/trace for the resumed execution
                    # We could link it to the original via metadata if needed
                    try:
                        original_trace_id = langfuse_info.get("trace_id")
                        langfuse_helper = LangfuseHelper.instance()
                        if langfuse_helper:
                            langfuse_span = langfuse_helper.trace(
                                name=f"Resumed: {playbook}",
                                metadata={
                                    "resumed_from_checkpoint": True,
                                    "original_trace_id": original_trace_id,
                                },
                            )
                    except Exception as e:
                        logger.debug(f"Could not create langfuse span on resume: {e}")
            else:
                # Old format: just instruction pointer dict
                instruction_pointer = InstructionPointer(
                    playbook=frame_dict.get("playbook"),
                    line_number=frame_dict.get("line_number"),
                    source_line_number=frame_dict.get("source_line_number", 0),
                )
                langfuse_span = None

            # Create CallStackFrame with langfuse span
            frame = CallStackFrame(
                instruction_pointer=instruction_pointer, langfuse_span=langfuse_span
            )

            # Push onto the call stack (without emitting events during restoration)
            agent.state.call_stack.frames.append(frame)
            frame.depth = len(agent.state.call_stack.frames)

        if call_stack_data:
            logger.info(
                f"Restored call stack with {len(call_stack_data)} frame(s): "
                f"{[frame.instruction_pointer.to_compact_str() for frame in agent.state.call_stack.frames]}"
            )
