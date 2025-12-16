"""Langfuse integration helper for LLM observability and tracing."""

import logging
import os
from typing import Any, Optional

from langfuse import Langfuse

from playbooks.config import config

# Suppress Langfuse context warnings since we use explicit parent-passing
# rather than automatic context tracking
logging.getLogger("langfuse").setLevel(logging.ERROR)


class PlaybooksLangfuseSpan:
    """No-op span implementation when Langfuse is disabled.

    Provides the same interface as Langfuse spans but performs no operations.
    Used when Langfuse telemetry is disabled via configuration.
    """

    def update(self, **kwargs: Any) -> "PlaybooksLangfuseSpan":
        """Update span metadata (no-op).

        Args:
            **kwargs: Metadata to update (ignored)

        Returns:
            Self for chaining
        """
        return self

    def end(self, **kwargs: Any) -> "PlaybooksLangfuseSpan":
        """End the span (no-op).

        Args:
            **kwargs: End parameters (ignored)

        Returns:
            Self for chaining
        """
        return self

    def start_generation(self, **kwargs: Any) -> "PlaybooksLangfuseSpan":
        """Start a generation (no-op).

        Args:
            **kwargs: Generation event data (ignored)

        Returns:
            No-op span
        """
        return PlaybooksLangfuseSpan()

    def start_span(self, **kwargs: Any) -> "PlaybooksLangfuseSpan":
        """Start a child span (no-op).

        Args:
            **kwargs: Span configuration (ignored)

        Returns:
            No-op span
        """
        return PlaybooksLangfuseSpan()

    def start_observation(self, **kwargs: Any) -> "PlaybooksLangfuseSpan":
        """Start a child observation (no-op).

        Args:
            **kwargs: Observation configuration (ignored)

        Returns:
            No-op span
        """
        return PlaybooksLangfuseSpan()

    def start_as_current_span(
        self, **kwargs: Any
    ) -> "PlaybooksLangfuseNoOpContextManager":
        """Start as current span (no-op).

        Args:
            **kwargs: Span configuration (ignored)

        Returns:
            No-op context manager
        """
        return PlaybooksLangfuseNoOpContextManager(PlaybooksLangfuseSpan())

    def start_as_current_observation(
        self, **kwargs: Any
    ) -> "PlaybooksLangfuseNoOpContextManager":
        """Start as current observation (no-op).

        Args:
            **kwargs: Observation configuration (ignored)

        Returns:
            No-op context manager
        """
        return PlaybooksLangfuseNoOpContextManager(PlaybooksLangfuseSpan())

    def score_trace(self, **kwargs: Any) -> "PlaybooksLangfuseSpan":
        """Score the trace (no-op).

        Args:
            **kwargs: Score parameters (ignored)

        Returns:
            Self for chaining
        """
        return self

    def update_trace(self, **kwargs: Any) -> "PlaybooksLangfuseSpan":
        """Update the trace (no-op).

        Args:
            **kwargs: Trace update parameters (ignored)

        Returns:
            Self for chaining
        """
        return self

    def trace(self, **kwargs: Any) -> "PlaybooksLangfuseSpan":
        """Create a trace (no-op).

        Args:
            **kwargs: Trace configuration (ignored)

        Returns:
            No-op span instance
        """
        return PlaybooksLangfuseSpan()


class PlaybooksLangfuseNoOpContextManager:
    """No-op context manager for langfuse observations."""

    def __init__(self, span: "PlaybooksLangfuseSpan"):
        self.span = span

    def __enter__(self) -> "PlaybooksLangfuseSpan":
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False


class PlaybooksLangfuseInstance:
    """No-op Langfuse instance when Langfuse is disabled.

    Provides the same interface as Langfuse client but performs no operations.
    Used when Langfuse telemetry is disabled via configuration.
    """

    def start_observation(self, **kwargs: Any) -> PlaybooksLangfuseSpan:
        """Create an observation (no-op).

        Args:
            **kwargs: Observation configuration (ignored)

        Returns:
            No-op span instance
        """
        return PlaybooksLangfuseSpan()

    def start_as_current_observation(
        self, **kwargs: Any
    ) -> PlaybooksLangfuseNoOpContextManager:
        """Create an observation as current (no-op).

        Args:
            **kwargs: Observation configuration (ignored)

        Returns:
            No-op context manager
        """
        return PlaybooksLangfuseNoOpContextManager(PlaybooksLangfuseSpan())

    def trace(self, **kwargs: Any) -> PlaybooksLangfuseSpan:
        """Create a trace (no-op).

        Args:
            **kwargs: Trace configuration (ignored)

        Returns:
            No-op span instance
        """
        return PlaybooksLangfuseSpan()

    def span(self, **kwargs: Any) -> PlaybooksLangfuseSpan:
        """Create a span (no-op).

        Args:
            **kwargs: Span configuration (ignored)

        Returns:
            No-op span instance
        """
        return PlaybooksLangfuseSpan()

    def update_current_span(self, **kwargs: Any) -> PlaybooksLangfuseSpan:
        """Update the current span (no-op)."""
        return PlaybooksLangfuseSpan()

    def get_current_span(self) -> PlaybooksLangfuseSpan:
        """Return the current span (no-op placeholder)."""
        return PlaybooksLangfuseSpan()

    def flush(self) -> None:
        """Flush pending events (no-op)."""
        pass

    def auth_check(self) -> bool:
        """Check authentication (no-op).

        Returns:
            True (always succeeds for no-op)
        """
        return True

    def update_current_trace(self, **kwargs: Any) -> None:
        """Update the current trace (no-op).

        Args:
            **kwargs: Trace update parameters (ignored)
        """
        pass


class LangfuseHelper:
    """A singleton helper class for Langfuse telemetry and tracing.

    This class provides centralized access to Langfuse for observability and
    tracing of LLM operations throughout the application.
    """

    langfuse: Langfuse | PlaybooksLangfuseInstance | None = None
    _session_id: Optional[str] = None  # Session ID for agent traces

    @classmethod
    def instance(cls) -> Langfuse | PlaybooksLangfuseInstance:
        """Get or initialize the Langfuse singleton instance.

        Creates the Langfuse client on first call using environment variables.
        Returns a no-op instance if Langfuse is disabled via configuration.

        Returns:
            Langfuse client instance or no-op instance if disabled
        """
        if cls.langfuse is None:
            # Check if Langfuse is enabled via config system first, then env fallback
            langfuse_enabled = False
            try:
                langfuse_enabled = config.langfuse.enabled
            except Exception:
                # Fallback to environment variable if config loading fails
                langfuse_enabled = (
                    os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
                )

            if not langfuse_enabled:
                cls.langfuse = PlaybooksLangfuseInstance()
            else:
                # Use v3 API - get_client() reads env vars automatically
                from langfuse import get_client

                cls.langfuse = get_client()
        return cls.langfuse

    @classmethod
    def flush(cls) -> None:
        """Flush any buffered Langfuse telemetry data to the server.

        This method should be called when immediate data transmission is needed,
        such as before application shutdown or after important operations.
        """
        if cls.langfuse:
            cls.langfuse.flush()

    @classmethod
    def set_session_id(cls, session_id: str) -> None:
        """Set the session ID for agent traces.

        Args:
            session_id: The session ID for this program execution
        """
        cls._session_id = session_id

    @classmethod
    def get_session_id(cls) -> Optional[str]:
        """Get the session ID for agent traces.

        Returns:
            The current session ID or None
        """
        return cls._session_id
