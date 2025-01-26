import os

# Default model to use if not specified
DEFAULT_MODEL = os.getenv("MODEL", "claude-3-5-sonnet-20241022")

INTERPRETER_TRACE_HEADER = "Playbooks interpreter trace"
