"""Tests for the CLI interface."""

from unittest.mock import AsyncMock, MagicMock, patch
from unittest.mock import call

import pytest
from typer.testing import CliRunner

from playbooks.cli.cli import app, _async_chat
from playbooks.cli.session import ChatSession


@pytest.fixture
def cli_runner():
    return CliRunner()


@pytest.fixture
def mock_session():
    with patch("playbooks.cli.cli.ChatSession") as mock:
        session_instance = AsyncMock(spec=ChatSession)
        mock.return_value = session_instance
        yield session_instance


@pytest.fixture
def mock_playbook_file(tmp_path):
    """Create a temporary playbook file for testing."""
    playbook = tmp_path / "test.yaml"
    playbook.write_text("name: test\ndescription: test playbook")
    return str(playbook)


def test_chat_command_basic(cli_runner, mock_playbook_file):
    """Test basic chat command with minimal arguments."""
    with patch("playbooks.cli.cli.ChatSession") as mock_session_cls, patch(
        "playbooks.cli.cli.Prompt.ask", return_value="exit"
    ):
        session_instance = AsyncMock()
        session_instance.initialize = AsyncMock()
        session_instance.process_user_input = AsyncMock(
            return_value=False
        )  # Exit after first message
        session_instance.cleanup = MagicMock()
        mock_session_cls.return_value = session_instance

        result = cli_runner.invoke(app, ["chat", mock_playbook_file])
        assert result.exit_code == 0

        # Verify ChatSession was created with correct args
        assert mock_session_cls.call_count == 1
        args = mock_session_cls.call_args[0]
        assert len(args[0]) == 2  # playbook_paths
        assert (
            args[0][1] == mock_playbook_file
        )  # Second arg is the actual playbook path
        assert args[1:] == (None, None, None, True)  # llm, model, api_key, stream

        session_instance.initialize.assert_awaited_once()
        session_instance.process_user_input.assert_has_awaits(
            [call("Begin"), call("exit")]
        )


def test_chat_command_with_options(cli_runner, mock_playbook_file):
    """Test chat command with all options specified."""
    with patch("playbooks.cli.cli.ChatSession") as mock_session_cls, patch(
        "playbooks.cli.cli.Prompt.ask", return_value="exit"
    ):
        session_instance = AsyncMock()
        session_instance.initialize = AsyncMock()
        session_instance.process_user_input = AsyncMock(
            return_value=False
        )  # Exit after first message
        session_instance.cleanup = MagicMock()
        mock_session_cls.return_value = session_instance

        result = cli_runner.invoke(
            app,
            [
                "chat",
                mock_playbook_file,
                "--llm",
                "openai",
                "--model",
                "gpt-4",
                "--api-key",
                "test-key",
                "--no-stream",
            ],
        )
        assert result.exit_code == 0

        # Verify ChatSession was created with correct args
        assert mock_session_cls.call_count == 1
        args = mock_session_cls.call_args[0]
        assert len(args[0]) == 2  # playbook_paths
        assert (
            args[0][1] == mock_playbook_file
        )  # Second arg is the actual playbook path
        assert args[1:] == (
            "openai",
            "gpt-4",
            "test-key",
            False,
        )  # llm, model, api_key, stream

        session_instance.initialize.assert_awaited_once()
        session_instance.process_user_input.assert_has_awaits(
            [call("Begin"), call("exit")]
        )


@pytest.mark.asyncio
async def test_async_chat_initialization(mock_session):
    """Test async chat initialization and cleanup."""
    playbook_paths = ["test.yaml"]

    # Simulate KeyboardInterrupt during chat
    mock_session.process_user_input.side_effect = KeyboardInterrupt()

    await _async_chat(
        playbook_paths=playbook_paths,
        llm="openai",
        model="gpt-4",
        api_key="test-key",
        stream=True,
    )

    # Verify initialization and cleanup
    mock_session.initialize.assert_called_once()
    mock_session.cleanup.assert_called_once()
    mock_session.process_user_input.assert_called_once_with("Begin")


@pytest.mark.asyncio
async def test_async_chat_error_handling(mock_session):
    """Test error handling in async chat."""
    playbook_paths = ["test.yaml"]

    # Simulate an error during chat
    mock_session.initialize.side_effect = Exception("Test error")

    with pytest.raises(Exception, match="Test error"):
        await _async_chat(
            playbook_paths=playbook_paths,
            llm=None,
            model=None,
            api_key=None,
            stream=True,
        )

    # Verify cleanup was called after error
    mock_session.cleanup.assert_called_once()


@pytest.mark.asyncio
async def test_async_chat_normal_flow(mock_session):
    """Test normal chat flow with multiple messages."""
    playbook_paths = ["test.yaml"]

    # Setup mock to handle one message then exit
    mock_session.process_user_input.side_effect = [True, False]

    with patch("playbooks.cli.cli.Prompt.ask", return_value="test message"):
        await _async_chat(
            playbook_paths=playbook_paths,
            llm=None,
            model=None,
            api_key=None,
            stream=True,
        )

    # Verify the expected calls
    assert mock_session.initialize.call_count == 1
    assert mock_session.process_user_input.call_count == 2  # Begin + test message
    assert mock_session.cleanup.call_count == 0  # No cleanup needed for normal exit
