import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from api.main import app

client = TestClient(app)

@pytest.fixture
def mock_env(monkeypatch):
    """Mock environment variables"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")

@pytest.fixture
def mock_playbook_runner():
    """Mock PlaybookRunner for testing"""
    with patch("api.main.PlaybookRunner") as mock:
        instance = mock.return_value
        instance.run.return_value = "Test response"
        yield mock

def test_health_check():
    """Test the health check endpoint"""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_run_playbook_success(mock_env, mock_playbook_runner):
    """Test successful playbook execution"""
    request_data = {
        "content": "test playbook",
        "llm_provider": "anthropic"
    }
    
    response = client.post("/api/run-playbook", json=request_data)
    assert response.status_code == 200
    assert response.json() == {"result": "Test response"}
    
    # Verify PlaybookRunner was called correctly
    mock_playbook_runner.assert_called_once()
    instance = mock_playbook_runner.return_value
    instance.run.assert_called_once_with(
        "test playbook", 
        user_input="Hello"
    )

def test_run_playbook_error(mock_env, mock_playbook_runner):
    """Test error handling in playbook execution"""
    # Make the runner raise an exception
    instance = mock_playbook_runner.return_value
    instance.run.side_effect = Exception("Test error")
    
    request_data = {
        "content": "test playbook",
        "llm_provider": "anthropic"
    }
    
    response = client.post("/api/run-playbook", json=request_data)
    assert response.status_code == 500
    assert response.json() == {"detail": "Test error"}

@pytest.fixture
def example_file():
    """Create a temporary example file in the correct location"""
    # Get the examples directory path relative to the API directory
    api_dir = os.path.dirname(os.path.dirname(__file__))
    examples_dir = os.path.join(os.path.dirname(api_dir), "examples")
    os.makedirs(examples_dir, exist_ok=True)
    test_file = os.path.join(examples_dir, "test.md")
    
    # Create test file
    with open(test_file, "w") as f:
        f.write("Test content")
        
    yield test_file
    
    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)

def test_get_example_success(example_file):
    """Test successful example retrieval"""
    response = client.get("/api/examples/test.md")
    assert response.status_code == 200
    assert response.json() == {"content": "Test content"}

def test_get_example_not_found():
    """Test example not found error"""
    response = client.get("/api/examples/nonexistent.md")
    assert response.status_code == 404
    assert response.json() == {"detail": "Example not found"}

def test_get_example_directory_traversal():
    """Test directory traversal prevention"""
    response = client.get("/api/examples/..%2F..%2Fetc%2Fpasswd")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
