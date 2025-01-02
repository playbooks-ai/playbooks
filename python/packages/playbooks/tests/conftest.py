import os

import pytest


@pytest.fixture(autouse=True)
def setup_test_env():
    """Setup test environment."""
    os.environ["ENVIRONMENT"] = "test"
