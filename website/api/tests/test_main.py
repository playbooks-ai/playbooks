from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app

# Create test client
client = TestClient(app)


@pytest.fixture
def mock_env(monkeypatch):
    """Mock environment variables"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")


@pytest.fixture
def mock_playbook_runner():
    """Mock PlaybooksRunner for testing"""
    with patch("api.main.PlaybooksRunner") as mock:
        instance = mock.return_value
        instance.run.return_value = "Test response"
        yield mock


def test_health_check():
    """Test the health check endpoint"""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_get_example_success():
    """Test successful example retrieval"""
    response = client.get("/api/examples/hello.md")
    assert response.status_code == 200
    assert response.json()["content"] is not None


def test_get_example_not_found():
    """Test example not found error"""
    response = client.get("/api/examples/nonexistent.md")
    assert response.status_code == 404
    assert response.json() == {"detail": "Example Not Found"}


def test_get_example_directory_traversal():
    """Test directory traversal prevention"""
    response = client.get("/api/examples/..%2F..%2Fetc%2Fpasswd")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
