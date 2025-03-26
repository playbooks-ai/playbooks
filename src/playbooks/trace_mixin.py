"""Unified tracing utilities for the playbooks package.

This module provides classes and functions for tracing execution in the playbooks system.
It includes a mixin class for adding tracing capabilities to other classes and a context
manager for tracing execution contexts.
"""

import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Union

from playbooks.interpreter.output_item import OutputItem, StringTrace


class TraceMixin:
    """A mixin class that provides tracing capabilities.

    This mixin adds methods for tracing execution and gathering trace metadata.
    Classes that inherit from this mixin can trace messages with metadata
    and log them for debugging and observability.

    Attributes:
        langfuse_span: Optional Langfuse span for tracing (expected to be set by inheriting classes).
    """

    def trace(
        self,
        message: Union[str, OutputItem],
        metadata: Optional[Dict[str, Any]] = None,
        level: str = "INFO",
    ) -> None:
        """Trace a message with metadata.

        Args:
            message: The message to trace, either a string or an OutputItem.
            metadata: Additional metadata to include in the trace.
            level: The log level for the trace.
        """
        if isinstance(message, str):
            message = StringTrace(message)

        # Update the trace metadata
        trace_metadata = metadata or {}
        trace_metadata.update({"level": level})

        # Set the metadata on the message
        message.metadata = trace_metadata

        # If langfuse tracing is enabled, create a span for this trace
        if hasattr(self, "langfuse_span") and self.langfuse_span:
            message.langfuse_span = self.langfuse_span.span(
                name=message.__repr__(), metadata=trace_metadata
            )

    def get_trace_metadata(self) -> Dict[str, Any]:
        """Get the trace metadata.

        Returns:
            The trace metadata for this object.
        """
        return {}

    def to_trace(self) -> Union[str, List]:
        """Convert to a trace representation.

        Returns:
            A string or list representation of this object for tracing.
        """
        return self.__repr__()

    def __repr__(self) -> str:
        return self.__class__.__name__


class TracingContext:
    """Context manager for tracing execution contexts.

    This class provides a context manager for tracing execution contexts,
    including timing and metadata. It automatically records the start and
    end of the context, along with timing information and any exceptions
    that occur during execution.

    Example:
        ```python
        with TracingContext(tracer, "process_request", {"request_id": "123"}):
            # Code to be traced
            process_request()
        ```
    """

    def __init__(
        self,
        tracer: TraceMixin,
        context_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the tracing context.

        Args:
            tracer: The tracer to use for tracing
            context_name: The name of the context
            metadata: Additional metadata to include in the trace
        """
        self.tracer = tracer
        self.context_name = context_name
        self.metadata = metadata or {}
        self.start_time = None

    def __enter__(self):
        """Enter the context manager.

        Records the start time and traces the start of the context.

        Returns:
            The tracing context
        """
        self.start_time = time.time()
        self.tracer.trace(
            f"Starting {self.context_name}",
            metadata=self.metadata,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager.

        Calculates the execution time, records any exceptions that occurred,
        and traces the end of the context.

        Args:
            exc_type: Exception type, if any
            exc_val: Exception value, if any
            exc_tb: Exception traceback, if any

        Returns:
            False to indicate that exceptions should not be suppressed
        """
        execution_time = time.time() - self.start_time

        # Prepare exit metadata
        exit_metadata = {
            **self.metadata,
            "execution_time": f"{execution_time:.2f}s",
        }

        # Add exception information if there was an exception
        if exc_val:
            exit_metadata["exception"] = str(exc_val)
            exit_metadata["exception_type"] = exc_type.__name__ if exc_type else None
            self.tracer.trace(
                f"Error in {self.context_name}: {exc_val}",
                metadata=exit_metadata,
                level="ERROR",
            )
        else:
            self.tracer.trace(
                f"Completed {self.context_name}",
                metadata=exit_metadata,
            )

        # Don't suppress exceptions
        return False

    def trace(self, message: str, additional_metadata: Optional[Dict[str, Any]] = None):
        """Trace a message within this context.

        Args:
            message: The message to trace
            additional_metadata: Additional metadata to include
        """
        metadata = {**self.metadata}
        if additional_metadata:
            metadata.update(additional_metadata)

        self.tracer.trace(f"{self.context_name}: {message}", metadata)


@contextmanager
def tracing_context(
    tracer: Optional[TraceMixin] = None,
    context_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Context manager for tracing execution.

    A convenience wrapper around TracingContext that can be used as a context manager.

    Args:
        tracer: The tracer to use for tracing
        context_name: The name of the context
        metadata: Additional metadata to include in the trace

    Yields:
        None
    """
    if tracer is not None and context_name is not None:
        with TracingContext(tracer, context_name, metadata):
            yield
    else:
        # Fall back to a no-op context manager if parameters are missing
        yield
