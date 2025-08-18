"""Tests for execution base module."""

from unittest.mock import Mock, patch

import pytest

from playbooks.execution.base import LLMExecution
from playbooks.utils.expression_engine import ExpressionContext


class ConcreteLLMExecution(LLMExecution):
    """Concrete implementation for testing."""

    async def execute(self, *args, **kwargs):
        """Test implementation of execute method."""
        return "executed"


class TestLLMExecution:
    """Test LLMExecution class."""

    def test_initialization(self):
        """Test LLMExecution initialization."""
        agent = Mock()
        playbook = Mock()
        playbook.name = "test_playbook"

        execution = ConcreteLLMExecution(agent, playbook)

        assert execution.agent == agent
        assert execution.playbook == playbook

    @pytest.mark.asyncio
    async def test_resolve_description_placeholders_no_placeholders(self):
        """Test resolve_description_placeholders with no placeholders."""
        agent = Mock()
        playbook = Mock()
        playbook.name = "test_playbook"

        execution = ConcreteLLMExecution(agent, playbook)

        # Test description without placeholders
        result = await execution.resolve_description_placeholders("Simple description")
        assert result == "Simple description"

        # Test empty description
        result = await execution.resolve_description_placeholders("")
        assert result == ""

        # Test None description
        result = await execution.resolve_description_placeholders(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_description_placeholders_with_placeholders(self):
        """Test resolve_description_placeholders with placeholders."""
        agent = Mock()
        agent.state = Mock()
        playbook = Mock()
        playbook.name = "test_playbook"

        execution = ConcreteLLMExecution(agent, playbook)

        description = "Hello {name}, your age is {age}"
        args = []
        kwargs = {"name": "Alice", "age": 30}

        # Mock the resolve_description_placeholders function
        with patch(
            "playbooks.execution.base.resolve_description_placeholders"
        ) as mock_resolve:
            mock_resolve.return_value = "Hello Alice, your age is 30"

            result = await execution.resolve_description_placeholders(
                description, *args, **kwargs
            )

            assert result == "Hello Alice, your age is 30"
            mock_resolve.assert_called_once()

            # Verify that PlaybookCall and ExpressionContext were created correctly
            call_args = mock_resolve.call_args
            assert call_args[0][0] == description  # First argument is description
            assert isinstance(call_args[0][1], ExpressionContext)  # Second is context

    @pytest.mark.asyncio
    async def test_resolve_description_placeholders_with_args(self):
        """Test resolve_description_placeholders with positional args."""
        agent = Mock()
        agent.state = Mock()
        playbook = Mock()
        playbook.name = "test_playbook"

        execution = ConcreteLLMExecution(agent, playbook)

        description = "Args: {arg1}, {arg2}"
        args = ["value1", "value2"]
        kwargs = {}

        with patch(
            "playbooks.execution.base.resolve_description_placeholders"
        ) as mock_resolve:
            mock_resolve.return_value = "Args: value1, value2"

            result = await execution.resolve_description_placeholders(
                description, *args, **kwargs
            )

            assert result == "Args: value1, value2"

            # Verify PlaybookCall was created with correct args
            call_args = mock_resolve.call_args
            context = call_args[0][1]
            assert isinstance(context, ExpressionContext)

    @pytest.mark.asyncio
    async def test_resolve_description_placeholders_exception_handling(self):
        """Test resolve_description_placeholders handles exceptions gracefully."""
        agent = Mock()
        agent.state = Mock()
        playbook = Mock()
        playbook.name = "test_playbook"

        execution = ConcreteLLMExecution(agent, playbook)

        description = "Hello {name}"

        # Mock the resolve function to raise an exception
        with patch(
            "playbooks.execution.base.resolve_description_placeholders"
        ) as mock_resolve:
            mock_resolve.side_effect = Exception("Resolution failed")

            # Mock logger to verify error is logged
            with patch("playbooks.execution.base.logging.getLogger") as mock_get_logger:
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger

                result = await execution.resolve_description_placeholders(description)

                # Should return original description on error
                assert result == description

                # Should log the error
                mock_logger.error.assert_called_once()
                assert "Failed to resolve description placeholders" in str(
                    mock_logger.error.call_args
                )

    @pytest.mark.asyncio
    async def test_resolve_description_placeholders_playbook_call_creation(self):
        """Test that PlaybookCall is created correctly."""
        agent = Mock()
        agent.state = Mock()
        playbook = Mock()
        playbook.name = "test_playbook"

        execution = ConcreteLLMExecution(agent, playbook)

        description = "Test {value}"
        args = ["arg1", "arg2"]
        kwargs = {"key1": "value1", "key2": "value2"}

        with patch("playbooks.execution.base.PlaybookCall") as mock_call_class:
            with patch(
                "playbooks.execution.base.ExpressionContext"
            ) as mock_context_class:
                with patch(
                    "playbooks.execution.base.resolve_description_placeholders"
                ) as mock_resolve:
                    mock_resolve.return_value = "Test resolved"

                    await execution.resolve_description_placeholders(
                        description, *args, **kwargs
                    )

                    # Verify PlaybookCall was created with correct parameters
                    mock_call_class.assert_called_once_with(
                        "test_playbook",
                        ["arg1", "arg2"],  # args as list
                        {"key1": "value1", "key2": "value2"},  # kwargs
                    )

                    # Verify ExpressionContext was created
                    mock_context_class.assert_called_once_with(
                        agent, agent.state, mock_call_class.return_value
                    )

    @pytest.mark.asyncio
    async def test_execute_is_abstract(self):
        """Test that execute method is abstract."""
        agent = Mock()
        playbook = Mock()

        # Cannot instantiate LLMExecution directly
        with pytest.raises(TypeError):
            LLMExecution(agent, playbook)

    @pytest.mark.asyncio
    async def test_concrete_execute(self):
        """Test concrete implementation of execute method."""
        agent = Mock()
        playbook = Mock()
        playbook.name = "test_playbook"

        execution = ConcreteLLMExecution(agent, playbook)

        result = await execution.execute("arg1", key="value")
        assert result == "executed"

    @pytest.mark.asyncio
    async def test_resolve_description_placeholders_edge_cases(self):
        """Test edge cases for resolve_description_placeholders."""
        agent = Mock()
        agent.state = Mock()
        playbook = Mock()
        playbook.name = "test_playbook"

        execution = ConcreteLLMExecution(agent, playbook)

        # Test with just opening brace (no closing brace)
        result = await execution.resolve_description_placeholders("Hello {incomplete")
        assert result == "Hello {incomplete"

        # Test with empty braces
        with patch(
            "playbooks.execution.base.resolve_description_placeholders"
        ) as mock_resolve:
            mock_resolve.return_value = "Hello "

            result = await execution.resolve_description_placeholders("Hello {}")
            assert result == "Hello "

    @pytest.mark.asyncio
    async def test_logger_usage(self):
        """Test that logger is properly used in exception handling."""
        agent = Mock()
        agent.state = Mock()
        playbook = Mock()
        playbook.name = "test_playbook"

        execution = ConcreteLLMExecution(agent, playbook)

        description = "Hello {name}"

        with patch(
            "playbooks.execution.base.resolve_description_placeholders"
        ) as mock_resolve:
            with patch("playbooks.execution.base.logging.getLogger") as mock_get_logger:
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger
                mock_resolve.side_effect = ValueError("Test error")

                await execution.resolve_description_placeholders(description)

                # Verify logger was requested with correct module name
                mock_get_logger.assert_called_once_with("playbooks.execution.base")

                # Verify error was logged with correct message
                mock_logger.error.assert_called_once()
                error_message = str(mock_logger.error.call_args[0][0])
                assert "Failed to resolve description placeholders" in error_message
                assert "Test error" in error_message
