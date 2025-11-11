"""End-to-end test for checkpoint resume functionality."""

import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from playbooks.checkpoints.filesystem import FilesystemCheckpointProvider
from playbooks.checkpoints.manager import CheckpointManager
from playbooks.checkpoints.recovery import RecoveryCoordinator
from playbooks.execution.streaming_python_executor import StreamingPythonExecutor


class TestEndToEndCheckpointResume:
    """Test complete checkpoint and resume cycle."""

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent with full state."""
        agent = MagicMock()
        agent.id = "test_agent_e2e"
        agent.state = MagicMock()
        agent.state.to_dict = MagicMock(return_value={"variables": {}})
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.to_dict = MagicMock(return_value=[])
        agent.state.call_stack.peek = MagicMock(
            return_value=MagicMock(langfuse_span=None)
        )
        agent.state.variables = MagicMock()
        agent.state.variables.to_dict = MagicMock(return_value={})
        agent.state.variables.__setitem__ = MagicMock()
        agent.state.variables.__getitem__ = MagicMock()
        agent.program = MagicMock()
        agent.program._debug_server = None
        agent.playbooks = {}
        agent.execute_playbook = AsyncMock(return_value=(True, ""))
        return agent

    @pytest.mark.asyncio
    async def test_complete_checkpoint_resume_cycle(self, mock_agent):
        """Test the complete cycle: execute, checkpoint, crash, resume.

        Scenario:
        1. Execute code with multiple await statements
        2. Checkpoint saved after each await
        3. Simulate crash mid-execution
        4. Resume from checkpoint
        5. Continue execution of remaining code
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            full_llm_response = """x = 10
await Say('user', 'Step 1: x is 10')
y = 20
await Say('user', 'Step 2: y is 20')
result = x + y
await Say('user', f'Final result: {result}')"""

            provider = FilesystemCheckpointProvider(base_path=tmpdir)
            manager = CheckpointManager(execution_id=mock_agent.id, provider=provider)

            executor1 = StreamingPythonExecutor(mock_agent)
            executor1.checkpoint_enabled = True
            executor1.checkpoint_manager = manager
            executor1.set_llm_response(full_llm_response)

            await executor1.add_chunk("x = 10\n")
            await executor1.add_chunk("await Say('user', 'Step 1: x is 10')\n")

            assert executor1.namespace["x"] == 10

            checkpoints = await provider.list_checkpoints(mock_agent.id)
            assert len(checkpoints) >= 1

            first_checkpoint_id = checkpoints[0]
            checkpoint1 = await provider.load_checkpoint(first_checkpoint_id)

            assert checkpoint1["namespace"]["x"] == 10
            assert checkpoint1["metadata"]["llm_response"] == full_llm_response
            assert "x = 10" in checkpoint1["metadata"]["executed_code"]

            latest_checkpoint = await manager.get_latest_checkpoint()

            executor2 = await StreamingPythonExecutor.resume_from_checkpoint(
                agent=mock_agent, checkpoint_data=latest_checkpoint
            )

            assert executor2.namespace["x"] == 10
            assert executor2._current_llm_response == full_llm_response

    @pytest.mark.asyncio
    async def test_resume_picks_up_where_left_off(self, mock_agent):
        """Test that resume continues from exact checkpoint without re-executing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            executed_code = "x = 10\nawait Say('user', 'hello')"
            full_response = """x = 10
await Say('user', 'hello')
y = 20
await Say('user', 'world')"""

            provider = FilesystemCheckpointProvider(base_path=tmpdir)

            checkpoint_data = {
                "checkpoint_id": "test_e2e_ckpt_1",
                "namespace": {"x": 10},
                "execution_state": {"variables": {"$x": 10}},
                "metadata": {
                    "llm_response": full_response,
                    "executed_code": executed_code,
                    "statement": "await Say('user', 'hello')",
                    "counter": 1,
                },
            }

            await provider.save_checkpoint(
                checkpoint_id=checkpoint_data["checkpoint_id"],
                execution_state=checkpoint_data["execution_state"],
                namespace=checkpoint_data["namespace"],
                metadata=checkpoint_data["metadata"],
            )

            executor = await StreamingPythonExecutor.resume_from_checkpoint(
                agent=mock_agent, checkpoint_data=checkpoint_data
            )

            assert executor.namespace["x"] == 10
            assert executor._current_llm_response == full_response

            # Resume executes remaining code, so executed_lines contains:
            # 1. Initial executed code (from checkpoint)
            # 2. Remaining code that was executed during resume
            assert executor.namespace["y"] == 20

    @pytest.mark.asyncio
    async def test_recovery_coordinator_end_to_end(self, mock_agent):
        """Test recovery coordinator orchestrates full recovery."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = FilesystemCheckpointProvider(base_path=tmpdir)
            manager = CheckpointManager(execution_id=mock_agent.id, provider=provider)
            coordinator = RecoveryCoordinator(manager)

            assert await coordinator.can_recover() is False

            await manager.save_checkpoint(
                statement_code="await Say('user', 'test')",
                namespace={"x": 42},
                execution_state={"variables": {"$x": 42}},
                call_stack=[],
                llm_response="x = 42\nawait Say('user', 'test')",
                executed_code="x = 42",
            )

            assert await coordinator.can_recover() is True

            info = await coordinator.get_recovery_info()
            assert info is not None
            assert info["statement"] == "await Say('user', 'test')"

            recovered = await coordinator.recover_execution_state(mock_agent)

            assert recovered["namespace"]["x"] == 42
            assert "llm_response" in recovered["metadata"]
            assert mock_agent.state.variables.__setitem__.called
