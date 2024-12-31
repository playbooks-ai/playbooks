import os
from pathlib import Path

import pytest
from dotenv import load_dotenv


@pytest.fixture(autouse=True)
def load_test_env():
    """Load test environment variables before each test."""
    env_file = Path(__file__).parent.parent / ".env.test"
    load_dotenv(env_file, override=True)

    # Ensure required test environment variables are set
    assert os.getenv("ENVIRONMENT") == "test", "Test environment not properly loaded"
