import os
from pathlib import Path

import pytest


def environment():
    from playbooks.utils.env_loader import load_environment

    load_environment()


os.environ["ENVIRONMENT"] = "test"
environment()


@pytest.fixture
def test_data_dir():
    """Fixture to provide path to test data directory"""
    return Path(__file__).parent / "data"


@pytest.fixture
def md_path(test_data_dir, md_file_name):
    md_path = test_data_dir / md_file_name

    assert md_path.exists()
    return md_path
