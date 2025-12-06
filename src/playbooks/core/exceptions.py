"""Custom exceptions for the playbooks package."""


class PlaybooksError(Exception):
    """Base exception class for all playbooks errors.

    All custom exceptions in the playbooks framework inherit from this class
    to allow catching all playbooks-specific errors.
    """


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


class CompilationError(PlaybooksError):
    """Raised when compilation fails due to LLM response issues.

    This can occur when the LLM response is truncated due to token limits
    or when the response content is empty/invalid.
    """

    pass


class ExecutionFinished(Exception):
    """Custom exception to indicate that the playbook execution is finished.

    This exception is raised to signal normal completion of playbook execution,
    allowing clean exit from execution loops and waiting operations.
    """


class KlassNotFoundError(PlaybooksError):
    """Raised when a klass is not found."""

    pass


class InteractiveInputRequired(PlaybooksError):
    """Raised when interactive input is required but non-interactive mode is set.

    This exception is used in CLI utility mode to signal that a playbook
    requires user interaction but the --non-interactive flag was specified.
    """

    pass
