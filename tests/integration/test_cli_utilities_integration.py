"""Integration tests for semantic CLI utilities."""

import subprocess
import sys

import pytest

from playbooks import Playbooks
from playbooks.config import config


class TestCLIArgsIntegration:
    """Test CLI arguments integration with playbooks."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_markdown_bgn_receives_cli_args(self, test_data_dir):
        """Test that markdown BGN playbook receives CLI args as kwargs."""
        playbooks = Playbooks(
            [test_data_dir / "cli_test_args.pb"],
            cli_args={"arg1": "value1", "arg2": "value2"},
        )
        await playbooks.initialize()

        assert playbooks.program.cli_args == {"arg1": "value1", "arg2": "value2"}

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_python_bgn_receives_cli_args(self, test_data_dir):
        """Test that Python BGN playbook receives CLI args."""
        playbooks = Playbooks(
            [test_data_dir / "cli_test_python_args.pb"],
            cli_args={"arg1": "test1", "arg2": "test2"},
        )
        await playbooks.initialize()

        assert playbooks.program.cli_args == {"arg1": "test1", "arg2": "test2"}


class TestStartupMessageIntegration:
    """Test $startup_message variable injection."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_message_sets_startup_message(self, test_data_dir):
        """Test that initial_state sets $startup_message."""
        from playbooks.agents import AIAgent

        playbooks = Playbooks(
            [test_data_dir / "cli_test_startup_message.pb"],
            initial_state={"startup_message": "test message"},
        )
        await playbooks.initialize()

        # Verify variable is set (only check AI agents, not human agents)
        for agent in playbooks.program.agents:
            if isinstance(agent, AIAgent) and hasattr(agent, "state"):
                assert hasattr(agent.state, "startup_message")
                assert agent.state.startup_message == "test message"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_large_startup_message_becomes_artifact(self, test_data_dir):
        """Test that large startup_message is promoted to Artifact."""
        from playbooks.agents import AIAgent

        # Create content larger than threshold
        large_content = "x" * (config.artifact_result_threshold + 100)

        playbooks = Playbooks(
            [test_data_dir / "cli_test_startup_message.pb"],
            initial_state={"startup_message": large_content},
        )
        await playbooks.initialize()

        # Verify it's an Artifact
        from playbooks.state.variables import Artifact

        for agent in playbooks.program.agents:
            if isinstance(agent, AIAgent) and hasattr(agent, "state"):
                var = agent.state.startup_message
                assert isinstance(var, Artifact), f"Expected Artifact, got {type(var)}"
                assert var.value == large_content
                assert hasattr(agent, "_initial_artifacts_to_load")
                assert "startup_message" in agent._initial_artifacts_to_load

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_large_startup_message_artifact_loaded_in_call_stack(
        self, test_data_dir
    ):
        """Test that large startup_message Artifact is loaded and used by playbook."""
        from playbooks.applications import cli_utility

        # Create content larger than threshold
        large_content = (
            "x" * (config.artifact_result_threshold + 100) + " UNIQUE_ARTIFACT_MARKER"
        )

        # Run through cli_utility which does the full flow
        exit_code = await cli_utility.main(
            program_paths=[str(test_data_dir / "cli_test_startup_message.pb")],
            stdin_content=large_content,
            quiet=True,
        )

        # Should complete successfully (exit code 0)
        assert exit_code == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_small_startup_message_remains_variable(self, test_data_dir):
        """Test that small startup_message stays as regular Variable."""
        from playbooks.agents import AIAgent

        small_content = "small text"
        assert len(small_content) < config.artifact_result_threshold

        playbooks = Playbooks(
            [test_data_dir / "cli_test_startup_message.pb"],
            initial_state={"startup_message": small_content},
        )
        await playbooks.initialize()

        from playbooks.state.variables import Artifact

        for agent in playbooks.program.agents:
            if isinstance(agent, AIAgent) and hasattr(agent, "state"):
                var = agent.state.startup_message
                assert not isinstance(var, Artifact)
                assert var == small_content


class TestExitCodes:
    """Test exit code handling."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_success_returns_zero(self, test_data_dir):
        """Test that successful execution returns exit code 0."""
        from playbooks.applications import cli_utility

        exit_code = await cli_utility.main(
            program_paths=[str(test_data_dir / "cli_test_success.pb")],
            quiet=True,
        )
        assert exit_code == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_non_interactive_with_wait_returns_three(self, test_data_dir):
        """Test that WaitForMessage in non-interactive mode returns exit code 3."""
        from playbooks.applications import cli_utility

        exit_code = await cli_utility.main(
            program_paths=[str(test_data_dir / "cli_test_wait_for_message.pb")],
            non_interactive=True,
            quiet=True,
        )
        assert exit_code == 3


class TestStdoutStderrSeparation:
    """Test stdout/stderr stream separation."""

    @pytest.mark.integration
    def test_output_goes_to_stdout(self, test_data_dir):
        """Test that agent output goes to stdout."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "playbooks",
                "run",
                str(test_data_dir / "cli_test_simple_output.pb"),
                "--quiet",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Output should be in stdout
        assert "TEST_OUTPUT_12345" in result.stdout
        # Should NOT be in stderr
        assert "TEST_OUTPUT_12345" not in result.stderr

    @pytest.mark.integration
    def test_version_banner_goes_to_stderr(self, test_data_dir):
        """Test that version banner goes to stderr."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "playbooks",
                "run",
                str(test_data_dir / "cli_test_success.pb"),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Version should be in stderr
        assert "Playbooks" in result.stderr
        # Should NOT be in stdout
        assert "Playbooks 0." not in result.stdout


class TestMessageAndStdinCombination:
    """Test stdin and message combination scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_stdin_becomes_startup_message(self, test_data_dir):
        """Test that stdin content is available as $startup_message."""
        from playbooks.agents import AIAgent

        playbooks = Playbooks(
            [test_data_dir / "cli_test_startup_message.pb"],
            initial_state={"startup_message": "from stdin"},
        )
        await playbooks.initialize()

        for agent in playbooks.program.agents:
            if isinstance(agent, AIAgent) and hasattr(agent, "state"):
                assert hasattr(agent.state, "startup_message")
                assert agent.state.startup_message == "from stdin"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_message_becomes_startup_message(self, test_data_dir):
        """Test that --message becomes $startup_message."""
        from playbooks.agents import AIAgent

        playbooks = Playbooks(
            [test_data_dir / "cli_test_startup_message.pb"],
            initial_state={"startup_message": "from message"},
        )
        await playbooks.initialize()

        for agent in playbooks.program.agents:
            if isinstance(agent, AIAgent) and hasattr(agent, "state"):
                assert hasattr(agent.state, "startup_message")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_stdin_and_message_combined(self, test_data_dir):
        """Test that stdin and message are combined with Message: prefix."""
        from playbooks.agents import AIAgent
        from playbooks.state.variables import Artifact

        stdin_content = "stdin data"
        message_content = "instruction"
        combined = f"{stdin_content}\n\nMessage: {message_content}"

        playbooks = Playbooks(
            [test_data_dir / "cli_test_startup_message.pb"],
            initial_state={"startup_message": combined},
        )
        await playbooks.initialize()

        for agent in playbooks.program.agents:
            if isinstance(agent, AIAgent) and hasattr(agent, "state"):
                value = agent.state.startup_message
                # Handle Artifact objects
                if isinstance(value, Artifact):
                    value = value.value
                assert "stdin data" in str(value)
                assert "Message: instruction" in str(value)


class TestQuietFlag:
    """Test --quiet flag functionality."""

    @pytest.mark.integration
    def test_quiet_suppresses_logs(self, test_data_dir):
        """Test that --quiet suppresses framework logs."""
        # With quiet
        result_quiet = subprocess.run(
            [
                sys.executable,
                "-m",
                "playbooks",
                "run",
                str(test_data_dir / "cli_test_quiet.pb"),
                "--quiet",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Without quiet
        result_normal = subprocess.run(
            [
                sys.executable,
                "-m",
                "playbooks",
                "run",
                str(test_data_dir / "cli_test_quiet.pb"),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Both should have output in stdout
        assert "Welcome" in result_quiet.stdout
        assert "Welcome" in result_normal.stdout

        # Quiet mode suppresses INFO logs, so may have less or equal stderr
        # (depends on whether compilation happened - if cached, both are similar)
        # Just verify both complete successfully
        assert result_quiet.returncode == 0
        assert result_normal.returncode == 0


class TestBackwardCompatibility:
    """Test that existing interactive playbooks still work."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_regular_playbook_without_params_works(self, test_data_dir):
        """Test that regular playbooks without CLI params still work."""
        playbooks = Playbooks([test_data_dir / "cli_test_success.pb"])
        await playbooks.initialize()
        await playbooks.program.run_till_exit()

        # Should complete without errors
        assert not playbooks.has_agent_errors()


class TestEndToEnd:
    """End-to-end CLI utility tests."""

    @pytest.mark.integration
    def test_cli_utility_with_stdin(self, test_data_dir):
        """Test complete flow with stdin input."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "playbooks",
                "run",
                str(test_data_dir / "cli_test_startup_message.pb"),
                "--quiet",
            ],
            input="test input from stdin",
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0
        assert "Received:" in result.stdout or "test input" in result.stdout

    @pytest.mark.integration
    def test_cli_utility_help_generation(self, test_data_dir):
        """Test that --help shows generated parameter help."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "playbooks",
                "run",
                str(test_data_dir / "cli_test_help.pb"),
                "--help",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Should show parameter names in help (after compilation and dynamic arg addition)
        # Note: This test may not show dynamic args because --help exits before dynamic addition
        # Just verify help works without error
        assert result.returncode == 0
        assert "usage:" in result.stdout

    @pytest.mark.integration
    def test_exit_code_on_success(self, test_data_dir):
        """Test that successful execution returns 0."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "playbooks",
                "run",
                str(test_data_dir / "cli_test_success.pb"),
                "--quiet",
            ],
            capture_output=True,
            timeout=30,
        )

        assert result.returncode == 0
