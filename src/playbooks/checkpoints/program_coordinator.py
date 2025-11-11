"""Program-level checkpoint coordination.

Manages checkpointing and recovery for entire Program executions,
coordinating checkpoints across all agents within the program.
"""

import logging
import re
import time
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

from playbooks.extensions.registry import ExtensionRegistry

if TYPE_CHECKING:
    from playbooks.program import Program

logger = logging.getLogger(__name__)


class ProgramCheckpointCoordinator:
    """Coordinates checkpoints for an entire Program and all its agents."""

    def __init__(self, program: "Program", session_id: str):
        """Initialize program checkpoint coordinator.

        Args:
            program: The Program instance to coordinate checkpoints for
            session_id: Unique session identifier for this program execution
        """
        self.program = program
        self.session_id = session_id
        self.checkpoint_counter = 0

        from playbooks.config import config

        provider_class = ExtensionRegistry._checkpoint_provider_class

        if provider_class:
            self.provider = provider_class(
                base_path=config.durability.storage_path,
                max_size_mb=config.durability.max_checkpoint_size_mb,
            )
        else:
            self.provider = None
            logger.warning("No checkpoint provider registered")

    def _get_program_execution_id(self) -> str:
        """Get the execution ID for program checkpoints.

        Program checkpoints use a separate execution ID namespace to avoid
        conflicts with agent checkpoints.

        Returns:
            Execution ID for program checkpoints
        """
        return f"{self.session_id}_program"

    def _parse_agent_info(self, agent_str: str) -> Optional[Tuple[str, str]]:
        """Parse klass and ID from agent string like 'Buyer(agent 1001)'.

        Args:
            agent_str: Agent string representation

        Returns:
            Tuple of (klass, agent_id) or None if parsing fails
        """
        match = re.match(r"(\w+)\(agent (\w+)\)", agent_str)
        if match:
            return (match.group(1), match.group(2))
        return None

    async def _create_agent_with_id(self, klass: str, agent_id: str) -> None:
        """Create agent with specific ID (for restoration).

        Args:
            klass: Agent class name
            agent_id: Specific agent ID to use
        """
        if klass not in self.program.agent_klasses:
            logger.error(f"Agent klass {klass} not found in program")
            return

        agent_class = self.program.agent_klasses[klass]

        # Create agent with specific ID (bypass registry)
        agent = agent_class(
            self.program.event_bus,
            agent_id,  # Use checkpoint ID, not registry
            program=self.program,
        )

        # Register agent
        self.program.agents.append(agent)
        if klass not in self.program.agents_by_klass:
            self.program.agents_by_klass[klass] = []
        self.program.agents_by_klass[klass].append(agent)
        self.program.agents_by_id[agent_id] = agent
        agent.program = self.program

        self.program.event_agents_changed()

        logger.info(f"🔧 Created agent {agent_id} (klass={klass}) for restoration")

    async def _ensure_agents_exist(self, agent_checkpoints: Dict[str, str]) -> None:
        """Create missing agents from checkpoints before restoration.

        Args:
            agent_checkpoints: Dict mapping agent_id to checkpoint_id
        """
        existing_ids = {a.id for a in self.program.agents if hasattr(a, "id")}

        for agent_id, checkpoint_id in agent_checkpoints.items():
            if agent_id in existing_ids:
                continue

            # Load checkpoint to get klass info
            checkpoint_data = await self.provider.load_checkpoint(checkpoint_id)
            if not checkpoint_data:
                logger.error(
                    f"Cannot load checkpoint {checkpoint_id} for agent {agent_id}"
                )
                continue

            # Get klass from execution_state agents list
            exec_state = checkpoint_data.get("execution_state", {})
            agents_list = exec_state.get("agents", [])

            klass = None
            for agent_str in agents_list:
                parsed = self._parse_agent_info(agent_str)
                if parsed and parsed[1] == agent_id:
                    klass = parsed[0]
                    break

            if not klass:
                logger.error(f"Cannot determine klass for agent {agent_id}")
                continue

            # Create agent with preserved ID
            await self._create_agent_with_id(klass, agent_id)

    async def save_program_checkpoint(self) -> Optional[str]:
        """Save a checkpoint for the entire program state.

        This captures:
        - All agent checkpoint IDs
        - Program-level state (meetings, coordination)
        - Session metadata

        Returns:
            Program checkpoint ID, or None if checkpointing unavailable
        """
        if not self.provider:
            return None

        self.checkpoint_counter += 1
        program_execution_id = self._get_program_execution_id()
        program_checkpoint_id = f"{program_execution_id}_ckpt_{self.checkpoint_counter}"

        # Collect all agent checkpoint IDs
        agent_checkpoints = {}
        for agent in self.program.agents:
            if hasattr(agent, "id"):
                # Get the agent's latest checkpoint
                agent_ckpts = await self.provider.list_checkpoints(agent.id)
                if agent_ckpts:
                    agent_checkpoints[agent.id] = agent_ckpts[-1]

        # Build program-level checkpoint metadata
        program_state = {
            "session_id": self.session_id,
            "checkpoint_counter": self.checkpoint_counter,
            "agent_checkpoints": agent_checkpoints,
            "agent_count": len(self.program.agents),
            "timestamp": time.time(),
        }

        try:
            await self.provider.save_checkpoint(
                checkpoint_id=program_checkpoint_id,
                execution_state={},  # Program doesn't have ExecutionState
                namespace={},  # Program-level has no namespace
                metadata=program_state,
            )

            logger.info(
                f"Program checkpoint saved: {program_checkpoint_id} "
                f"(agents: {list(agent_checkpoints.keys())})"
            )

            return program_checkpoint_id
        except Exception as e:
            logger.error(f"Failed to save program checkpoint: {e}")
            return None

    async def restore_program_checkpoint(self) -> bool:
        """Restore the entire program from the latest checkpoint.

        This:
        1. Finds the latest program checkpoint
        2. Restores all agents from their respective checkpoints
        3. Restores program-level coordination state
        4. Sets checkpoint counter to continue from where we left off

        Returns:
            True if restoration succeeded, False otherwise
        """
        if not self.provider:
            logger.warning("No checkpoint provider available for restore")
            return False

        # Find latest program checkpoint for this session
        program_execution_id = self._get_program_execution_id()
        program_checkpoints = await self.provider.list_checkpoints(program_execution_id)
        if not program_checkpoints:
            logger.info(f"No program checkpoints found for session {self.session_id}")
            return False

        latest_program_ckpt = program_checkpoints[-1]
        program_data = await self.provider.load_checkpoint(latest_program_ckpt)

        # Resume checkpoint counter from where we left off
        if program_data and "metadata" in program_data:
            restored_counter = program_data["metadata"].get("checkpoint_counter", 0)
            self.checkpoint_counter = restored_counter
            logger.info(
                f"Resuming checkpoint counter from {restored_counter} "
                f"(latest checkpoint: {latest_program_ckpt})"
            )

        if not program_data:
            logger.error(f"Failed to load program checkpoint {latest_program_ckpt}")
            return False

        program_metadata = program_data.get("metadata", {})
        agent_checkpoints = program_metadata.get("agent_checkpoints", {})

        logger.info(
            f"Restoring program from checkpoint: {latest_program_ckpt} "
            f"(agents: {list(agent_checkpoints.keys())})"
        )

        # Ensure all agents exist before restoring
        await self._ensure_agents_exist(agent_checkpoints)

        # Get the LATEST checkpoint for each agent (program checkpoint may be stale)
        latest_agent_checkpoints = {}
        for agent_id in agent_checkpoints.keys():
            agent_ckpts = await self.provider.list_checkpoints(agent_id)
            if agent_ckpts:
                latest_agent_checkpoints[agent_id] = agent_ckpts[-1]
                if latest_agent_checkpoints[agent_id] != agent_checkpoints[agent_id]:
                    logger.info(
                        f"Using latest checkpoint {latest_agent_checkpoints[agent_id]} "
                        f"for agent {agent_id} (program checkpoint had {agent_checkpoints[agent_id]})"
                    )
            else:
                latest_agent_checkpoints[agent_id] = agent_checkpoints[agent_id]

        # Restore each agent from its LATEST checkpoint
        restored_agents = []

        for agent in self.program.agents:
            if hasattr(agent, "id") and agent.id in latest_agent_checkpoints:
                agent_ckpt_id = latest_agent_checkpoints[agent.id]

                try:
                    # Load agent checkpoint
                    agent_data = await self.provider.load_checkpoint(agent_ckpt_id)

                    if agent_data:
                        # Restore agent state
                        from playbooks.checkpoints.recovery import RecoveryCoordinator
                        from playbooks.checkpoints.manager import CheckpointManager

                        manager = CheckpointManager(
                            execution_id=agent.id, provider=self.provider
                        )
                        coordinator = RecoveryCoordinator(manager)

                        await coordinator.recover_execution_state(agent)

                        # Resume streaming executor if there's an LLM response
                        if agent_data["metadata"].get("llm_response"):
                            from playbooks.execution.streaming_python_executor import (
                                StreamingPythonExecutor,
                            )

                            await StreamingPythonExecutor.resume_from_checkpoint(
                                agent=agent, checkpoint_data=agent_data
                            )

                        restored_agents.append(agent.id)
                        logger.info(
                            f"✅ Agent {agent.id} restored from {agent_ckpt_id}"
                        )
                    else:
                        logger.warning(
                            f"Could not load checkpoint data for agent {agent.id}"
                        )

                except Exception as e:
                    logger.error(
                        f"Failed to restore agent {agent.id}: {e}", exc_info=True
                    )

        total_agents = len(agent_checkpoints)
        restored_count = len(restored_agents)

        logger.info(
            f"Program restoration complete: {restored_count}/{total_agents} agents restored"
        )

        return restored_count > 0

    async def can_resume(self) -> bool:
        """Check if there are program checkpoints available for resume.

        Returns:
            True if program checkpoints exist, False otherwise
        """
        if not self.provider:
            return False

        program_execution_id = self._get_program_execution_id()
        program_checkpoints = await self.provider.list_checkpoints(program_execution_id)
        return len(program_checkpoints) > 0

    async def get_resume_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the latest program checkpoint.

        Returns:
            Dictionary with checkpoint metadata, or None if no checkpoints exist
        """
        if not self.provider:
            return None

        program_execution_id = self._get_program_execution_id()
        program_checkpoints = await self.provider.list_checkpoints(program_execution_id)
        if not program_checkpoints:
            return None

        latest_ckpt = program_checkpoints[-1]
        program_data = await self.provider.load_checkpoint(latest_ckpt)

        if program_data:
            metadata = program_data.get("metadata", {})
            return {
                "checkpoint_id": latest_ckpt,
                "session_id": metadata.get("session_id"),
                "checkpoint_counter": metadata.get("checkpoint_counter"),
                "agent_count": metadata.get("agent_count"),
                "agents": list(metadata.get("agent_checkpoints", {}).keys()),
                "timestamp": metadata.get("timestamp"),
            }

        return None
