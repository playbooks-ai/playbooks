import os
from pathlib import Path

import pytest


def environment():
    from playbooks.utils.env_loader import load_environment

    load_environment()


# Set test profile for playbooks config system
os.environ["ENVIRONMENT"] = "test"
os.environ["PLAYBOOKS_PROFILE"] = "test"
environment()


# Pytest hooks to control LLM call behavior based on test type
def pytest_runtest_setup(item):
    """Set environment variable to control LLM calls based on test location.

    Unit tests (in tests/unit/) are not allowed to make real LLM calls.
    Integration tests (in tests/integration/) can make real LLM calls.

    Note: Using _ALLOW_LLM_CALLS prefix (not PLAYBOOKS_) to avoid being picked up
    by the Playbooks config loader which auto-loads PLAYBOOKS_* env vars.
    """
    test_file_path = str(item.fspath)

    if "/tests/unit/" in test_file_path or "\\tests\\unit\\" in test_file_path:
        # Unit test - block real LLM calls
        os.environ["_ALLOW_LLM_CALLS"] = "false"
    elif (
        "/tests/integration/" in test_file_path
        or "\\tests\\integration\\" in test_file_path
    ):
        # Integration test - allow real LLM calls
        os.environ["_ALLOW_LLM_CALLS"] = "true"
    else:
        # Default: allow LLM calls for other test locations
        os.environ["_ALLOW_LLM_CALLS"] = "true"


def pytest_runtest_teardown(item):
    """Clean up environment variable after test."""
    # Remove the flag to avoid any cross-test contamination
    os.environ.pop("_ALLOW_LLM_CALLS", None)


@pytest.fixture
def test_data_dir():
    """Fixture to provide path to test data directory"""
    return Path(__file__).parent / "data"


@pytest.fixture
def test_examples_dir():
    """Fixture to provide path to test examples directory"""
    return Path(__file__).parent.parent / "examples"


@pytest.fixture
def md_path(test_data_dir, md_file_name):
    md_path = test_data_dir / md_file_name

    assert md_path.exists()
    return md_path


# MCP Server fixtures for testing
@pytest.fixture
def test_mcp_server():
    """Pytest fixture for the test MCP server."""
    from tests.unit.applications.test_mcp_server import get_test_server

    server = get_test_server()
    server.reset_data()  # Reset data for each test
    return server


@pytest.fixture
def test_mcp_server_instance():
    """Pytest fixture that returns the FastMCP server instance."""
    from tests.unit.applications.test_mcp_server import get_test_server

    server = get_test_server()
    server.reset_data()
    return server.get_server()


def extract_messages_from_cli_output(output: str) -> list[str]:
    """Extract message content from CLI output.

    Supports multiple formats:
    1. Old format: 💬 HelloWorld(1000) → User: Hello! Welcome to the Playbooks system!
    2. New format: [HelloWorld(1000) → User] followed by message on next line(s)
    3. Message content without headers (fallback for when stdout/stderr are separated)

    Returns list of message contents.
    """
    messages = []
    lines = output.split("\n")

    current_message = None
    in_message_header = False
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Check for old format: 💬 Sender → Recipient: message
        if "💬" in line and "→" in line and ":" in line:
            if current_message:
                messages.append(current_message)
            parts = line.split(":", 1)
            if len(parts) == 2:
                current_message = parts[1].strip()
            in_message_header = False

        # Check for new format: [Sender → Recipient]
        elif stripped.startswith("[") and "→" in line and stripped.endswith("]"):
            if current_message:
                messages.append(current_message)
            current_message = None
            in_message_header = True

        # If we just saw a header, the next non-empty line is the message content
        elif in_message_header and stripped:
            current_message = stripped
            in_message_header = False

        # Continuation of current message
        elif current_message and stripped and not in_message_header:
            # Only add if it doesn't start a new section
            if not line.startswith(
                ("Error", "💬", "[", "---", "Playbooks", "ℹ", "poetry")
            ):
                current_message += " " + stripped

        # Fallback: if we have content that looks like a message (doesn't look like metadata or a header)
        # and we're not currently tracking a message, start a new one
        # This handles the case where stdout and stderr are separated and messages come without headers
        elif (
            stripped
            and not in_message_header
            and not current_message
            and not stripped.startswith(("[", "---", "Playbooks", "ℹ", "poetry"))
            and "→" not in stripped  # Not a header itself
            and "Loading" not in stripped
            and "Execution" not in stripped
            and len(stripped) > 20  # Likely to be actual message content
        ):
            # Start a new message
            if current_message:
                messages.append(current_message)
            current_message = stripped

        i += 1

    # Add the last message if any
    if current_message:
        messages.append(current_message)

    return messages
