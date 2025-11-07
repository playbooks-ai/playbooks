"""Tests for using Artifacts in messages (e.g., Say)."""

from playbooks.state.variables import Artifact


class TestArtifactConversion:
    """Test that Artifact objects can be converted to message strings."""

    def test_artifact_has_len_through_content(self):
        """Test that we can get length from an Artifact's value."""
        artifact = Artifact(
            name="test_report",
            summary="A test report",
            value="This is the full content of the report.",
        )

        # Convert artifact to string using value
        message_str = str(artifact.value)

        # Verify we can call len() on the result
        assert len(message_str) == len("This is the full content of the report.")
        assert message_str == "This is the full content of the report."

    def test_artifact_str_vs_content(self):
        """Test that str(artifact) returns the value (artifact behaves like its value)."""
        artifact = Artifact(
            name="report", summary="Summary of report", value="Full content here"
        )

        # str(artifact) gives the value (artifact behaves like a string of its value)
        assert str(artifact) == "Full content here"

        # str(artifact.value) also gives the actual value
        assert str(artifact.value) == "Full content here"

        # They should be equal since artifact exposes itself as its value
        assert str(artifact) == str(artifact.value)

    def test_artifact_with_complex_content(self):
        """Test artifacts with different value types."""
        # String value
        artifact1 = Artifact(name="text", summary="Text artifact", value="Hello world")
        assert str(artifact1.value) == "Hello world"

        # Number value (will be converted to string)
        artifact2 = Artifact(name="number", summary="Number artifact", value=42)
        assert str(artifact2.value) == "42"

        # Dict value (will be converted to string representation)
        artifact3 = Artifact(
            name="data", summary="Data artifact", value={"key": "value"}
        )
        assert "key" in str(artifact3.value)
        assert "value" in str(artifact3.value)
