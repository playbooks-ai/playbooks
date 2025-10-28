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
