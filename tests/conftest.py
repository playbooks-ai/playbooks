import os
from pathlib import Path

import pytest

os.environ["ENVIRONMENT"] = "test"


@pytest.fixture
def test_data_dir():
    """Fixture to provide path to test data directory"""
    return Path(__file__).parent / "data"
