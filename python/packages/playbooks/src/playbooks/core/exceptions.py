"""Custom exceptions for the playbooks package."""


class PlaybooksError(Exception):
    """Base exception class for all playbooks errors."""

    pass


class AgentError(PlaybooksError):
    """Base exception class for agent-related errors."""

    pass


class AgentConfigurationError(AgentError):
    """Raised when there is an error in agent configuration."""

    pass


class AgentAlreadyRunningError(AgentError):
    """Raised when attempting to run an agent that is already running."""

    pass


class RuntimeError(PlaybooksError):
    """Base exception class for runtime-related errors."""

    pass


class PlaybookError(PlaybooksError):
    """Base exception class for playbook-related errors."""

    pass


class DatabaseError(PlaybooksError):
    """Base exception class for database-related errors."""

    pass
