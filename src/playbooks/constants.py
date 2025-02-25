import os

# Default model to use if not specified
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "claude-3-5-sonnet-20241022")

SYSTEM_PROMPT_DELIMITER = "====SYSTEM_PROMPT_DELIMITER===="
