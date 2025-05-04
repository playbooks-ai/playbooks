"""Custom exceptions for the playbooks package."""


class PlaybooksError(Exception):
    """Base exception class for all playbooks errors."""

    pass


class ProgramLoadError(PlaybooksError):
    """Exception raised when there is an error loading a program."""

    pass


class AgentError(PlaybooksError):
    """Base exception class for agent-related errors."""

    pass


class AgentConfigurationError(AgentError):
    """Raised when there is an error in agent configuration."""

    pass


class VendorAPIOverloadedError(PlaybooksError):
    """Raised when the vendor API is overloaded."""

    pass


class VendorAPIRateLimitError(PlaybooksError):
    """Raised when the vendor API rate limit is exceeded."""

    pass
