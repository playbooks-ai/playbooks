"""Langfuse integration helper for LLM observability and tracing."""

import os
from typing import Any

from langfuse import Langfuse

from ..config import config


class PlaybooksLangfuseSpan:
    """No-op span implementation when Langfuse is disabled.

    Provides the same interface as Langfuse spans but performs no operations.
    Used when Langfuse telemetry is disabled via configuration.
    """

    def update(self, **kwargs: Any) -> None:
        """Update span metadata (no-op).

        Args:
            **kwargs: Metadata to update (ignored)
        """
        pass

    def generation(self, **kwargs: Any) -> None:
        """Log generation event (no-op).

        Args:
            **kwargs: Generation event data (ignored)
        """
        pass

    def span(self, **kwargs: Any) -> "PlaybooksLangfuseSpan":
        """Create a child span (no-op, returns self).

        Args:
            **kwargs: Span configuration (ignored)

        Returns:
            Self (no-op span)
        """
        return PlaybooksLangfuseSpan()


class PlaybooksLangfuseInstance:
    """No-op Langfuse instance when Langfuse is disabled.

    Provides the same interface as Langfuse client but performs no operations.
    Used when Langfuse telemetry is disabled via configuration.
    """

    def trace(self, **kwargs: Any) -> PlaybooksLangfuseSpan:
        """Create a trace span (no-op).

        Args:
            **kwargs: Trace configuration (ignored)

        Returns:
            No-op span instance
        """
        return PlaybooksLangfuseSpan()

    def flush(self) -> None:
        """Flush pending events (no-op)."""
        pass


class LangfuseHelper:
    """A singleton helper class for Langfuse telemetry and tracing.

    This class provides centralized access to Langfuse for observability and
    tracing of LLM operations throughout the application.
    """

    langfuse: Langfuse | None = None

    @classmethod
    def instance(cls) -> Langfuse | PlaybooksLangfuseInstance | None:
        """Get or initialize the Langfuse singleton instance.

        Creates the Langfuse client on first call using environment variables.
        Returns a no-op instance if Langfuse is disabled via configuration.

        Returns:
            Langfuse client instance, no-op instance if disabled, or None
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
                cls.langfuse = Langfuse(
                    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
                    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
                    host=os.getenv("LANGFUSE_HOST"),
                )
        return cls.langfuse

    @classmethod
    def flush(cls) -> None:
        """Flush any buffered Langfuse telemetry data to the server.

        This method should be called when immediate data transmission is needed,
        such as before application shutdown or after important operations.
        """
        if cls.langfuse:
            cls.langfuse.flush()
