"""Tests for VariablesTracker.public_variables() utility method."""

import pytest
from dotmap import DotMap

from playbooks.state.variables import Artifact, VariablesTracker


@pytest.fixture
def variables():
    """Create a DotMap instance for testing."""
    return DotMap()


class TestPublicVariables:
    """Test VariablesTracker.public_variables() method."""

    def test_public_variables_excludes_underscore_vars(self, variables):
        """Test that public_variables() excludes variables starting with _."""
        # Add public variables (no $ prefix in new system)
        variables.user_name = "Alice"
        variables.order_id = "12345"
        variables.total = 99.99

        # Add private variables (starting with _)
        variables._internal = "private"
        variables.__execution = "summary"

        # Get public variables
        public_vars = VariablesTracker.public_variables(variables)

        # Verify public variables are included
        assert "user_name" in public_vars
        assert "order_id" in public_vars
        assert "total" in public_vars

        # Verify private variables are excluded
        assert "_internal" not in public_vars
        assert "__execution" not in public_vars

        # Verify count
        assert len(public_vars) == 3

    def test_public_variables_returns_raw_values(self, variables):
        """Test that public_variables() returns raw values (no Variable wrapper)."""
        variables.test = "value"

        public_vars = VariablesTracker.public_variables(variables)

        assert "test" in public_vars
        assert public_vars["test"] == "value"

    def test_public_variables_empty_when_only_private(self, variables):
        """Test that public_variables() returns empty dict when only private vars exist."""
        # Add only private variables
        variables._private = "secret"
        variables.__internal = "data"

        public_vars = VariablesTracker.public_variables(variables)

        assert len(public_vars) == 0
        assert public_vars == {}

    def test_public_variables_includes_all_when_no_private(self, variables):
        """Test that public_variables() includes all vars when none are private."""
        variables.a = "value_a"
        variables.b = "value_b"
        variables.c = "value_c"

        public_vars = VariablesTracker.public_variables(variables)

        assert len(public_vars) == 3
        assert all(key in public_vars for key in ["a", "b", "c"])

    def test_public_variables_with_artifacts(self, variables):
        """Test that public_variables() works with artifact variables."""
        # Create an artifact (no $ prefix)
        artifact = Artifact(name="result", summary="Test result", value="content")
        variables.result = artifact

        public_vars = VariablesTracker.public_variables(variables)

        assert "result" in public_vars
        assert isinstance(public_vars["result"], Artifact)
        assert public_vars["result"].summary == "Test result"

    def test_public_variables_excludes_underscore(self, variables):
        """Test that _ is correctly excluded as a private variable."""
        variables._ = "last result"
        variables.answer = "public answer"

        public_vars = VariablesTracker.public_variables(variables)

        # _ should be excluded (private)
        assert "_" not in public_vars
        # answer should be included (public)
        assert "answer" in public_vars
        assert len(public_vars) == 1

    def test_public_variables_with_none_values(self, variables):
        """Test that public_variables() excludes None values."""
        variables.value = None
        variables._private = None
        variables.has_value = "test"

        public_vars = VariablesTracker.public_variables(variables)

        # None values excluded
        assert "value" not in public_vars
        # Private variable should also be excluded
        assert "_private" not in public_vars
        # Non-None public value included
        assert "has_value" in public_vars
