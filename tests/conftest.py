import pytest
from pathlib import Path

@pytest.fixture
def test_data_dir():
    """Fixture to provide path to test data directory"""
    return Path(__file__).parent / "data"

# Add more fixtures here as needed
