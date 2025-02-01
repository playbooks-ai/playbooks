import os
from pathlib import Path

from dotenv import load_dotenv


def load_environment(env_name: str = None) -> None:
    """
    Load environment variables from .env files with proper precedence.

    Args:
        env_name: Optional environment name ('development', 'test', 'production')
                 If None, will try to use ENV or ENVIRONMENT environment variable,
                 falling back to 'development'
    """
    base_path = Path(__file__).parent.parent.parent.parent

    # First load the base .env file if it exists
    base_env = base_path / ".env"
    if base_env.exists():
        load_dotenv(base_env)

    # Determine environment
    if not env_name:
        env_name = os.getenv("ENV") or os.getenv("ENVIRONMENT") or "development"

    # Load environment-specific file if it exists
    env_file = base_path / f".env.{env_name}"
    if env_file.exists():
        load_dotenv(env_file, override=True)  # Override any existing variables
