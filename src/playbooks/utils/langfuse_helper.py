import os
from typing import Any

from langfuse import Langfuse


class MockLangfuseSpan:
    def update(self, **kwargs: Any) -> None:
        pass

    def generation(self, **kwargs: Any) -> None:
        pass

    def span(self, **kwargs: Any) -> None:
        return MockLangfuseSpan()


class MockLangfuseInstance:
    def trace(self, **kwargs: Any) -> None:
        return MockLangfuseSpan()

    def flush(self) -> None:
        pass


class LangfuseHelper:
    """A singleton helper class for Langfuse telemetry and tracing.

    This class provides centralized access to Langfuse for observability and
    tracing of LLM operations throughout the application.
    """

    langfuse: Langfuse | None = None

    @classmethod
    def instance(cls) -> Langfuse | None:
        """Get or initialize the Langfuse singleton instance.

        Creates the Langfuse client on first call using environment variables.
        Returns None if environment variables are not set.

        Returns:
            Langfuse: The initialized Langfuse client instance, or None
        """
        if cls.langfuse is None:
            if os.getenv("LANGFUSE_ENABLED", "false").lower() == "false":
                cls.langfuse = MockLangfuseInstance()
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
