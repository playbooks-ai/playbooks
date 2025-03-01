"""Step execution module for the interpreter."""

from typing import Any, Dict

import yaml

from ..trace_mixin import TraceMixin


class StepExecution(TraceMixin):
    """Represents the execution of a step in a playbook."""

    def __init__(
        self,
        step: str,
        metadata: Dict[str, Any] = None,
    ):
        """Initialize a step execution.

        Args:
            step: The step to execute.
            metadata: Metadata about the step.
        """
        super().__init__()
        self.step = step
        self.metadata = metadata

    def __repr__(self):
        """Return a string representation of the step execution."""
        return yaml.dump(self.metadata).strip()
