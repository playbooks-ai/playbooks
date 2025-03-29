"""Step execution module for the interpreter.

This module provides the StepExecution class that represents the execution of a
playbook step and provides tracing functionality.
"""

import json
from typing import Any, Dict, List, Optional, Union

from playbooks.trace_mixin import TraceMixin


class StepExecution(TraceMixin):
    """Represents the execution of a step in a playbook.

    This class tracks the execution of a step and its associated metadata
    for tracing and debugging purposes.

    Attributes:
        step: The step identifier to execute.
        metadata: Additional metadata about the step execution.
        langfuse_span: Optional span for Langfuse tracing.
    """

    def __init__(
        self,
        step: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize a step execution.

        Args:
            step: The step identifier to execute.
            metadata: Metadata about the step execution.
        """
        super().__init__()
        self.step = step
        self.metadata = metadata or {}  # Initialize to empty dict if None
        self.langfuse_span = None  # Initialize langfuse_span attribute

    def get_trace_metadata(self) -> Dict[str, Any]:
        """Get metadata for tracing.

        Returns:
            Dictionary containing step execution metadata for tracing.
        """
        return {
            "step": self.step,
            **self.metadata,
        }

    def to_trace(self) -> Union[str, List]:
        """Convert to a trace representation.

        Returns:
            A trace representation of this step execution.
        """
        return f"StepExecution(step={self.step})"

    def __repr__(self) -> str:
        """Return a string representation of the step execution.

        Returns:
            A formatted string with step identifier and metadata.
        """
        metadata_str = json.dumps(self.metadata, indent=2).strip()
        return f"StepExecution(step={self.step}, metadata={metadata_str})"
