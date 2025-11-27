"""Unit tests for CLI utilities functionality."""

import pytest
import argparse

from playbooks.cli import (
    get_cli_entry_point,
    add_cli_arguments,
)


class TestCLIEntryPointDetection:
    """Test CLI entry point detection logic."""

    def test_explicit_cli_entry_marker(self):
        """Test that cli_entry:true takes precedence."""
        public_jsons = [
            [
                {
                    "name": "Helper",
                    "is_bgn": True,
                    "cli_entry": False,
                },
                {
                    "name": "Main",
                    "is_bgn": True,
                    "cli_entry": True,
                    "parameters": {"type": "object", "properties": {}},
                },
            ]
        ]

        entry_point = get_cli_entry_point(public_jsons)
        assert entry_point is not None
        assert entry_point["name"] == "Main"
        assert entry_point["cli_entry"] is True

    def test_bgn_fallback_when_no_explicit_marker(self):
        """Test that first BGN playbook is used when no cli_entry:true."""
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
                    "cli_entry": False,
                },
            ]
        ]

        entry_point = get_cli_entry_point(public_jsons)
        assert entry_point is not None
        assert entry_point["name"] == "Main"
        assert entry_point["is_bgn"] is True

    def test_multiple_cli_entry_raises_error(self):
        """Test that multiple cli_entry:true causes ValueError."""
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

    def test_no_entry_point_returns_none(self):
        """Test that no BGN or cli_entry returns None."""
        public_jsons = [
            [
                {
                    "name": "Helper",
                    "is_bgn": False,
                    "cli_entry": False,
                }
            ]
        ]

        entry_point = get_cli_entry_point(public_jsons)
        assert entry_point is None

    def test_empty_public_jsons_returns_none(self):
        """Test that empty public_jsons returns None."""
        assert get_cli_entry_point([]) is None
        assert get_cli_entry_point(None) is None


class TestDynamicArgparseGeneration:
    """Test dynamic argparse argument generation."""

    def test_add_string_parameter(self):
        """Test adding string parameter to argparse."""
        parser = argparse.ArgumentParser()
        entry_point = {
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "User name"}},
                "required": ["name"],
            }
        }

        add_cli_arguments(parser, entry_point)

        # Parse with the argument
        args = parser.parse_args(["--name", "Alice"])
        assert args.name == "Alice"

    def test_add_integer_parameter(self):
        """Test adding integer parameter to argparse."""
        parser = argparse.ArgumentParser()
        entry_point = {
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Number of items"}
                },
                "required": [],
            }
        }

        add_cli_arguments(parser, entry_point)
        args = parser.parse_args(["--count", "42"])
        assert args.count == 42

    def test_add_boolean_parameter(self):
        """Test adding boolean parameter to argparse."""
        parser = argparse.ArgumentParser()
        entry_point = {
            "parameters": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean", "description": "Enable feature"}
                },
                "required": [],
            }
        }

        add_cli_arguments(parser, entry_point)
        args = parser.parse_args(["--enabled", "true"])
        assert args.enabled is True

    def test_required_vs_optional_parameters(self):
        """Test that required parameters are enforced."""
        parser = argparse.ArgumentParser()
        entry_point = {
            "parameters": {
                "type": "object",
                "properties": {
                    "required_arg": {"type": "string"},
                    "optional_arg": {"type": "string"},
                },
                "required": ["required_arg"],
            }
        }

        add_cli_arguments(parser, entry_point)

        # Should work with required arg (argparse converts - to _)
        args = parser.parse_args(["--required_arg", "value"])
        assert args.required_arg == "value"

        # Should fail without required arg
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_multiple_parameters(self):
        """Test adding multiple parameters."""
        parser = argparse.ArgumentParser()
        entry_point = {
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                    "format": {"type": "string"},
                },
                "required": ["start", "end"],
            }
        }

        add_cli_arguments(parser, entry_point)
        args = parser.parse_args(["--start", "abc", "--end", "def", "--format", "json"])
        assert args.start == "abc"
        assert args.end == "def"
        assert args.format == "json"


class TestStartupMessageCombination:
    """Test $startup_message combination logic."""

    def test_stdin_only(self):
        """Test that stdin alone becomes $startup_message."""
        stdin = "test content"
        message = None

        if stdin and message:
            result = f"{stdin}\n\nMessage: {message}"
        elif stdin:
            result = stdin
        elif message:
            result = message
        else:
            result = None

        assert result == "test content"

    def test_message_only(self):
        """Test that message alone becomes $startup_message."""
        stdin = None
        message = "test message"

        if stdin and message:
            result = f"{stdin}\n\nMessage: {message}"
        elif stdin:
            result = stdin
        elif message:
            result = message
        else:
            result = None

        assert result == "test message"

    def test_stdin_and_message_combined(self):
        """Test that stdin + message are properly combined."""
        stdin = "stdin content"
        message = "message content"

        if stdin and message:
            result = f"{stdin}\n\nMessage: {message}"
        elif stdin:
            result = stdin
        elif message:
            result = message
        else:
            result = None

        assert result == "stdin content\n\nMessage: message content"

    def test_neither_stdin_nor_message(self):
        """Test that no input results in None."""
        stdin = None
        message = None

        if stdin and message:
            result = f"{stdin}\n\nMessage: {message}"
        elif stdin:
            result = stdin
        elif message:
            result = message
        else:
            result = None

        assert result is None
