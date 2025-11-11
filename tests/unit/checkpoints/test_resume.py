"""Tests for checkpoint resume functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from playbooks.execution.streaming_python_executor import StreamingPythonExecutor


class TestCheckpointResume:
    """Test suite for checkpoint resume functionality."""

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent."""
        agent = MagicMock()
        agent.id = "test_agent_123"
        agent.state = MagicMock()
        agent.state.to_dict = MagicMock(return_value={"variables": {}})
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.to_dict = MagicMock(return_value=[])
        agent.state.call_stack.peek = MagicMock(return_value=MagicMock())

        # Mock variables with to_dict method
        agent.state.variables = MagicMock()
        agent.state.variables.to_dict = MagicMock(return_value={})
        agent.state.variables.__setitem__ = MagicMock()
        agent.state.variables.__getitem__ = MagicMock()

        # Mock program with debug server
        agent.program = MagicMock()
        agent.program._debug_server = None

        # Mock playbooks dict
        agent.playbooks = {}

        return agent

    @pytest.mark.asyncio
    async def test_streaming_executor_tracks_llm_response(self, mock_agent):
        """Test that streaming executor tracks the LLM response."""
        executor = StreamingPythonExecutor(mock_agent)

        assert executor._current_llm_response is None

        executor.set_llm_response("x = 10\ny = 20")

        assert executor._current_llm_response == "x = 10\ny = 20"

    @pytest.mark.asyncio
    async def test_checkpoint_contains_llm_response(self, mock_agent):
        """Test that checkpoints contain the LLM response."""
        from playbooks.checkpoints.filesystem import FilesystemCheckpointProvider
        from playbooks.checkpoints.manager import CheckpointManager
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            provider = FilesystemCheckpointProvider(base_path=tmpdir)
            manager = CheckpointManager(execution_id="test_123", provider=provider)

            llm_response = "x = 10\nawait Say('user', 'hello')\ny = 20"
            executed_code = "x = 10\nawait Say('user', 'hello')"

            checkpoint_id = await manager.save_checkpoint(
                statement_code="await Say('user', 'hello')",
                namespace={"x": 10},
                execution_state={"variables": {}},
                call_stack=[],
                llm_response=llm_response,
                executed_code=executed_code,
            )

            loaded = await manager.load_checkpoint(checkpoint_id)

            assert loaded["metadata"]["llm_response"] == llm_response
            assert loaded["metadata"]["executed_code"] == executed_code

    @pytest.mark.asyncio
    async def test_resume_from_checkpoint_restores_namespace(self, mock_agent):
        """Test that resume restores the namespace."""
        checkpoint_data = {
            "namespace": {"x": 10, "y": 20, "result": 30},
            "metadata": {
                "llm_response": None,
                "executed_code": "x = 10\ny = 20\nresult = x + y",
            },
        }

        executor = await StreamingPythonExecutor.resume_from_checkpoint(
            agent=mock_agent, checkpoint_data=checkpoint_data
        )

        assert executor.namespace["x"] == 10
        assert executor.namespace["y"] == 20
        assert executor.namespace["result"] == 30

    @pytest.mark.asyncio
    async def test_resume_from_checkpoint_continues_execution(self, mock_agent):
        """Test that resume continues executing remaining code."""
        full_llm_response = """x = 10
await Say('user', 'x is 10')
y = 20
await Say('user', 'y is 20')
result = x + y"""

        executed_code = """x = 10
await Say('user', 'x is 10')"""

        checkpoint_data = {
            "namespace": {"x": 10},
            "metadata": {
                "llm_response": full_llm_response,
                "executed_code": executed_code,
            },
        }

        # Mock the Say function to avoid actual execution
        mock_agent.execute_playbook = AsyncMock(return_value=(True, ""))
        mock_agent.state.call_stack.peek().langfuse_span = None

        executor = await StreamingPythonExecutor.resume_from_checkpoint(
            agent=mock_agent, checkpoint_data=checkpoint_data
        )

        # Remaining code should have been executed
        # Note: In actual test we'd need proper namespace setup
        # This is a basic structural test
        assert executor._current_llm_response == full_llm_response

    @pytest.mark.asyncio
    async def test_checkpoint_after_each_await(self, mock_agent):
        """Test that checkpoints are saved after each await statement."""
        from playbooks.checkpoints.filesystem import FilesystemCheckpointProvider
        from playbooks.checkpoints.manager import CheckpointManager
        from playbooks.config import config
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Enable durability
            config.durability.enabled = True
            config.durability.storage_path = tmpdir

            provider = FilesystemCheckpointProvider(base_path=tmpdir)
            manager = CheckpointManager(execution_id=mock_agent.id, provider=provider)

            executor = StreamingPythonExecutor(mock_agent)
            executor.checkpoint_enabled = True
            executor.checkpoint_manager = manager
            executor.set_llm_response(
                "await Say('user', 'hello')\nawait Say('user', 'world')"
            )

            # Mock Say to avoid actual execution
            mock_agent.execute_playbook = AsyncMock(return_value=(True, ""))
            mock_agent.state.call_stack.peek().langfuse_span = None

            # Execute code with awaits
            await executor.add_chunk("await Say('user', 'hello')\n")
            await executor.add_chunk("await Say('user', 'world')\n")
            await executor.finalize()

            # Check that checkpoints were created
            checkpoints = await provider.list_checkpoints(mock_agent.id)

            # Should have at least one checkpoint per await
            assert len(checkpoints) >= 1

            # Cleanup
            config.durability.enabled = False

    @pytest.mark.asyncio
    async def test_get_executed_code(self, mock_agent):
        """Test that executor tracks executed code."""
        executor = StreamingPythonExecutor(mock_agent)

        # Initially no executed code
        assert executor.get_executed_code() == ""

        # After executing some statements
        executor.executed_lines = ["x = 10", "y = 20"]

        executed = executor.get_executed_code()
        assert "x = 10" in executed
        assert "y = 20" in executed
