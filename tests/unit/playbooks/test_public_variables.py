"""Tests for Variables.public_variables() method."""

from unittest.mock import Mock

import pytest

from playbooks.event_bus import EventBus
from playbooks.variables import Artifact, Variables


@pytest.fixture
def event_bus():
    """Create a mock event bus."""
    return Mock(spec=EventBus)


@pytest.fixture
def variables(event_bus):
    """Create a Variables instance."""
    return Variables(event_bus, "test_agent")


class TestPublicVariables:
    """Test Variables.public_variables() method."""

    def test_public_variables_excludes_underscore_vars(self, variables):
        """Test that public_variables() excludes variables starting with $_."""
        # Add public variables
        variables["$user_name"] = "Alice"
        variables["$order_id"] = "12345"
        variables["$total"] = 99.99

        # Add private variables (starting with $_)
        variables["$_internal"] = "private"
        variables["$__execution"] = "summary"

        # Get public variables
        public_vars = variables.public_variables()

        # Verify public variables are included
        assert "$user_name" in public_vars
        assert "$order_id" in public_vars
        assert "$total" in public_vars

        # Verify private variables are excluded
        assert "$_internal" not in public_vars
        assert "$__execution" not in public_vars

        # Verify count
        assert len(public_vars) == 3

    def test_public_variables_returns_variable_objects(self, variables):
        """Test that public_variables() returns Variable objects."""
        from playbooks.variables import Variable

        variables["$test"] = "value"

        public_vars = variables.public_variables()

        assert "$test" in public_vars
        assert isinstance(public_vars["$test"], Variable)
        assert public_vars["$test"].value == "value"

    def test_public_variables_empty_when_only_private(self, variables):
        """Test that public_variables() returns empty dict when only private vars exist."""
        # Add only private variables
        variables["$_private"] = "secret"
        variables["$__internal"] = "data"

        public_vars = variables.public_variables()

        assert len(public_vars) == 0
        assert public_vars == {}

    def test_public_variables_includes_all_when_no_private(self, variables):
        """Test that public_variables() includes all vars when none are private."""
        variables["$a"] = "value_a"
        variables["$b"] = "value_b"
        variables["$c"] = "value_c"

        public_vars = variables.public_variables()

        assert len(public_vars) == 3
        assert all(key in public_vars for key in ["$a", "$b", "$c"])

    def test_public_variables_with_artifacts(self, variables):
        """Test that public_variables() works with artifact variables."""
        # Create an artifact
        artifact = Artifact(name="result", summary="Test result", value="content")
        variables["$result"] = artifact

        public_vars = variables.public_variables()

        assert "$result" in public_vars
        assert isinstance(public_vars["$result"].value, Artifact)
        assert public_vars["$result"].value.summary == "Test result"

    def test_public_variables_excludes_dollar_underscore(self, variables):
        """Test that $_ is correctly excluded as a private variable."""
        variables["$_"] = "last result"
        variables["$answer"] = "public answer"

        public_vars = variables.public_variables()

        # $_ should be excluded (private)
        assert "$_" not in public_vars
        # $answer should be included (public)
        assert "$answer" in public_vars
        assert len(public_vars) == 1

    def test_public_variables_with_none_values(self, variables):
        """Test that public_variables() includes variables with None values."""
        variables["$value"] = None
        variables["$_private"] = None

        public_vars = variables.public_variables()

        # Public variable with None should be included
        assert "$value" in public_vars
        assert public_vars["$value"].value is None

        # Private variable should still be excluded
        assert "$_private" not in public_vars
