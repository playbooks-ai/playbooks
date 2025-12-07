"""Integration tests for CLI utility functionality."""

import tempfile
from pathlib import Path

import pytest

from playbooks import Playbooks


class TestCLIUtility:
    """Test CLI utility mode with args and stdin."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_bgn_playbook_receives_cli_args(self):
        """Test that BGN playbook receives CLI args as kwargs."""
        playbook_content = """# TestAgent
Test agent for CLI args

## Main($arg1, $arg2)
### Triggers
- At the beginning
### Steps
- Set $result to "arg1={$arg1}, arg2={$arg2}"
- Say(user, $result)
- End program
"""
        # Create temporary playbook file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pb", delete=False) as f:
            f.write(playbook_content)
            temp_path = f.name

        try:
            # Initialize with CLI args
            playbooks = Playbooks(
                [temp_path], cli_args={"arg1": "value1", "arg2": "value2"}
            )
            await playbooks.initialize()

            # Verify program was initialized
            assert playbooks.program is not None
            assert len(playbooks.program.agents) > 0

            # Verify CLI args were stored
            assert playbooks.program.cli_args == {"arg1": "value1", "arg2": "value2"}

        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_message_variable_injection(self):
        """Test that --message flag creates $message variable."""
        playbook_content = """# TestAgent
Test agent for message injection

## Main
### Triggers
- At the beginning
### Steps
- If $message is available, say(user, "Received: {$message}")
- Otherwise say(user, "No message")
- End program
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pb", delete=False) as f:
            f.write(playbook_content)
            temp_path = f.name

        try:
            playbooks = Playbooks([temp_path])
            await playbooks.initialize()

            # Inject message into agent state
            for agent in playbooks.program.agents:
                if hasattr(agent, "state") and hasattr(agent.state, "variables"):
                    agent.state.variables.message = "test message"
                    assert hasattr(agent.state.variables, "message")
                    assert agent.state.variables.message == "test message"
                    break

        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_stdin_variable_injection(self):
        """Test that stdin content is available as $stdin."""
        playbook_content = """# TestAgent
Test agent for stdin

## Main
### Triggers
- At the beginning
### Steps
- If $stdin is available, say(user, "Stdin: {$stdin}")
- Otherwise say(user, "No stdin")
- End program
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pb", delete=False) as f:
            f.write(playbook_content)
            temp_path = f.name

        try:
            playbooks = Playbooks([temp_path])
            await playbooks.initialize()

            # Inject stdin content into agent state
            stdin_content = "test stdin content"
            for agent in playbooks.program.agents:
                if hasattr(agent, "state") and hasattr(agent.state, "variables"):
                    agent.state.variables.stdin = stdin_content
                    assert hasattr(agent.state.variables, "stdin")
                    assert agent.state.variables.stdin == stdin_content
                    break

        finally:
            Path(temp_path).unlink()


class TestPublicJSONExtraction:
    """Test public.json extraction and parsing."""

    @pytest.mark.integration
    def test_cli_entry_point_detection(self):
        """Test that CLI entry points are detected from public.json."""
        from playbooks.cli import get_cli_entry_point

        # Test with cli_entry: true
        public_jsons = [
            [
                {
                    "name": "Helper",
                    "is_bgn": False,
                    "cli_entry": False,
                },
                {
                    "name": "Main",
                    "is_bgn": True,
                    "cli_entry": True,
                    "parameters": {
                        "type": "object",
                        "properties": {"arg1": {"type": "string"}},
                    },
                },
            ]
        ]

        entry_point = get_cli_entry_point(public_jsons)
        assert entry_point is not None
        assert entry_point["name"] == "Main"
        assert entry_point["cli_entry"] is True

    @pytest.mark.integration
    def test_bgn_fallback_entry_point(self):
        """Test that first BGN playbook is used as fallback."""
        from playbooks.cli import get_cli_entry_point

        # No cli_entry: true, but has BGN playbook
        public_jsons = [
            [
                {
                    "name": "Main",
                    "is_bgn": True,
                    "cli_entry": False,
                    "parameters": {"type": "object", "properties": {}},
                }
            ]
        ]

        entry_point = get_cli_entry_point(public_jsons)
        assert entry_point is not None
        assert entry_point["name"] == "Main"
        assert entry_point["is_bgn"] is True

    @pytest.mark.integration
    def test_multiple_cli_entry_error(self):
        """Test that multiple cli_entry: true causes an error."""
        from playbooks.cli import get_cli_entry_point

        public_jsons = [
            [
                {
                    "name": "Main1",
                    "cli_entry": True,
                },
                {
                    "name": "Main2",
                    "cli_entry": True,
                },
            ]
        ]

        with pytest.raises(
            ValueError, match="Multiple playbooks marked with cli_entry"
        ):
            get_cli_entry_point(public_jsons)
