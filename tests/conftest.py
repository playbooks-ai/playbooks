import os
from pathlib import Path

import pytest

from playbooks.utils.env_loader import load_environment

os.environ["ENVIRONMENT"] = "test"
load_environment()


@pytest.fixture
def test_data_dir():
    """Fixture to provide path to test data directory"""
    return Path(__file__).parent / "data"
