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
    from tests.unit.playbooks.test_mcp_server import get_test_server

    server = get_test_server()
    server.reset_data()  # Reset data for each test
    return server


@pytest.fixture
def test_mcp_server_instance():
    """Pytest fixture that returns the FastMCP server instance."""
    from tests.unit.playbooks.test_mcp_server import get_test_server

    server = get_test_server()
    server.reset_data()
    return server.get_server()


def extract_messages_from_cli_output(output: str) -> list[str]:
    """Extract message content from CLI output.

    Parses lines like:
    💬 HelloWorld(1000) → User: Hello! Welcome to the Playbooks system!

    Returns list of message contents (the part after the colon).
    """
    messages = []
    # Pattern to match message lines: 💬 Sender → Recipient: message
    # The message might span multiple lines if wrapped
    lines = output.split("\n")

    current_message = None
    for line in lines:
        # Check if this is a message line (starts with 💬)
        if "💬" in line and "→" in line and ":" in line:
            # Extract the message content (everything after the last colon)
            parts = line.split(":", 1)
            if len(parts) == 2:
                message_content = parts[1].strip()
                if current_message:
                    messages.append(current_message)
                current_message = message_content
        elif current_message and line.strip():
            # Continuation of previous message (wrapped line)
            # Only add if it doesn't start a new section (like "Error" or another message)
            if not line.startswith(("Error", "💬", "---", "Playbooks")):
                current_message += " " + line.strip()

    # Add the last message if any
    if current_message:
        messages.append(current_message)

    return messages
