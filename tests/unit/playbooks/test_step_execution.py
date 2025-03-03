"""Tests for the StepExecution class."""

import json

from playbooks.interpreter import StepExecution


class TestStepExecution:
    """Tests for the StepExecution class."""

    def test_initialization(self):
        """Test that the StepExecution class initializes correctly."""
        step = "TestPlaybook:01:CMD"
        metadata = {
            "TestPlaybook:01:CMD": [
                {"call": {"fn": "Say", "args": [], "kwargs": {"message": "Hello"}}}
            ]
        }
        step_execution = StepExecution(step, metadata)

        assert step_execution.step == step
        assert step_execution.metadata == metadata
        assert hasattr(step_execution, "_trace_items")

    def test_repr(self):
        """Test that the __repr__ method returns the expected string."""
        step = "TestPlaybook:01:CMD"
        metadata = {
            "TestPlaybook:01:CMD": [
                {"call": {"fn": "Say", "args": [], "kwargs": {"message": "Hello"}}}
            ]
        }
        step_execution = StepExecution(step, metadata)

        expected_repr = json.dumps(metadata, indent=2).strip()
        assert repr(step_execution) == expected_repr
