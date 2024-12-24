import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Default model to use if not specified
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "claude-3-5-sonnet-20241022")
