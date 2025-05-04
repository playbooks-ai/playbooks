import os
from pathlib import Path

from dotenv import load_dotenv


def load_environment(env_name: str = None) -> None:
    """
    Load environment variables from .env files with proper precedence.

    First loads the base .env file (if it exists), then overrides with
    environment-specific variables from .env.[environment] file.

    Args:
        env_name: Environment name ('development', 'test', 'production').
                 If None, uses ENV or ENVIRONMENT variable, defaulting to 'development'
    """
    # Find root project directory (4 levels up from this file)
    root_dir = Path(__file__).parents[3]

    # Load base .env file if it exists
    base_env_path = root_dir / ".env"
    if base_env_path.exists():
        load_dotenv(base_env_path)

    # Determine environment name
    env_name = env_name or os.getenv("ENV") or os.getenv("ENVIRONMENT") or "development"

    # Load environment-specific file with higher precedence
    env_specific_path = root_dir / f".env.{env_name}"
    # print(f"Loading environment variables from {env_specific_path}")
    if env_specific_path.exists():
        load_dotenv(env_specific_path, override=True)

    # print(f"Environment variables: {os.environ}")
