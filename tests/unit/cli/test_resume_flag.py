"""Tests for CLI --resume flag."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestCLIResumeFlag:
    """Test suite for --resume CLI flag."""

    @pytest.mark.asyncio
    async def test_resume_flag_passed_to_application(self):
        """Test that --resume flag is passed to application."""
        from playbooks.cli import run_application

        with patch("playbooks.cli.importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_module.main = AsyncMock()
            mock_import.return_value = mock_module

            with patch("playbooks.cli.LLMConfig"):
                await run_application(
                    application_module="playbooks.applications.agent_chat",
                    program_paths=["test.pb"],
                    resume=True,
                )

                mock_module.main.assert_called_once()
                call_kwargs = mock_module.main.call_args.kwargs
                assert call_kwargs["resume"] is True

    @pytest.mark.asyncio
    async def test_resume_flag_defaults_to_false(self):
        """Test that resume defaults to False when not specified."""
        from playbooks.cli import run_application

        with patch("playbooks.cli.importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_module.main = AsyncMock()
            mock_import.return_value = mock_module

            with patch("playbooks.cli.LLMConfig"):
                await run_application(
                    application_module="playbooks.applications.agent_chat",
                    program_paths=["test.pb"],
                    resume=False,
                )

                call_kwargs = mock_module.main.call_args.kwargs
                assert call_kwargs["resume"] is False
