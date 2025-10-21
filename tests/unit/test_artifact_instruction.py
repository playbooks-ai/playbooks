"""Tests for the new Artifact instruction syntax."""

import pytest

from playbooks.event_bus import EventBus
from playbooks.llm_response_line import LLMResponseLine
from playbooks.variables import Artifact


class MockAgent:
    """Mock agent for testing."""

    def __init__(self):
        self.id = "test-agent"
        self.state = None

    def parse_instruction_pointer(self, step):
        """Mock parse_instruction_pointer."""
        return step


@pytest.fixture
def event_bus():
    return EventBus(session_id="test-session")


@pytest.fixture
def mock_agent():
    return MockAgent()


@pytest.mark.asyncio
class TestArtifactInstruction:
    """Test suite for Artifact instruction syntax."""

    async def test_artifact_instruction_basic(self, event_bus, mock_agent):
        """Test basic Artifact instruction parsing."""
        response_text = '`Artifact[$report, "Summary", """Content here"""]`'

        line = await LLMResponseLine.create(response_text, event_bus, mock_agent)

        assert "$report" in line.vars
        artifact = line.vars["$report"].value
        assert isinstance(artifact, Artifact)
        assert artifact.summary == "Summary"
        assert artifact.value == "Content here"
        assert artifact.name == "report"

    async def test_artifact_instruction_multiline_content(self, event_bus, mock_agent):
        """Test Artifact instruction with multi-line content."""
        response_text = '`Artifact[$doc, "Document", """Line 1\nLine 2\nLine 3"""]`'

        line = await LLMResponseLine.create(response_text, event_bus, mock_agent)

        assert "$doc" in line.vars
        artifact = line.vars["$doc"].value
        assert isinstance(artifact, Artifact)
        assert artifact.summary == "Document"
        assert artifact.value == "Line 1\nLine 2\nLine 3"

    async def test_artifact_instruction_with_special_chars(self, event_bus, mock_agent):
        """Test Artifact instruction with special characters in summary."""
        response_text = (
            '`Artifact[$data, "Q3 Report: Sales & Marketing", """Revenue: $100K"""]`'
        )

        line = await LLMResponseLine.create(response_text, event_bus, mock_agent)

        assert "$data" in line.vars
        artifact = line.vars["$data"].value
        assert isinstance(artifact, Artifact)
        assert artifact.summary == "Q3 Report: Sales & Marketing"
        assert artifact.value == "Revenue: $100K"

    async def test_var_with_triple_quotes_not_artifact(self, event_bus, mock_agent):
        """Test that Var with triple quotes creates a string, not artifact."""
        response_text = '`Var[$text, """Multi\nLine\nString"""]`'

        line = await LLMResponseLine.create(response_text, event_bus, mock_agent)

        assert "$text" in line.vars
        value = line.vars["$text"].value
        # Should be a plain string, not an Artifact
        assert not isinstance(value, Artifact)
        assert isinstance(value, str)
        assert value == "Multi\nLine\nString"

    async def test_artifact_and_var_together(self, event_bus, mock_agent):
        """Test Artifact and Var instructions on same line."""
        response_text = (
            '`Artifact[$art, "Summary", """Content"""]` `Var[$str, """String"""]`'
        )

        line = await LLMResponseLine.create(response_text, event_bus, mock_agent)

        # Should have both variables
        assert "$art" in line.vars
        assert "$str" in line.vars

        # $art should be an Artifact
        artifact = line.vars["$art"].value
        assert isinstance(artifact, Artifact)
        assert artifact.summary == "Summary"
        assert artifact.value == "Content"

        # $str should be a plain string
        string_val = line.vars["$str"].value
        assert not isinstance(string_val, Artifact)
        assert string_val == "String"

    async def test_artifact_with_empty_content(self, event_bus, mock_agent):
        """Test Artifact instruction with empty content."""
        response_text = '`Artifact[$empty, "Empty artifact", """"""]`'

        line = await LLMResponseLine.create(response_text, event_bus, mock_agent)

        assert "$empty" in line.vars
        artifact = line.vars["$empty"].value
        assert isinstance(artifact, Artifact)
        assert artifact.summary == "Empty artifact"
        assert artifact.value == ""

    async def test_multiple_artifacts_same_line(self, event_bus, mock_agent):
        """Test multiple Artifact instructions on same line."""
        response_text = '`Artifact[$a1, "First", """Content 1"""]` `Artifact[$a2, "Second", """Content 2"""]`'

        line = await LLMResponseLine.create(response_text, event_bus, mock_agent)

        # Should have both artifacts
        assert "$a1" in line.vars
        assert "$a2" in line.vars

        artifact1 = line.vars["$a1"].value
        assert isinstance(artifact1, Artifact)
        assert artifact1.summary == "First"
        assert artifact1.value == "Content 1"

        artifact2 = line.vars["$a2"].value
        assert isinstance(artifact2, Artifact)
        assert artifact2.summary == "Second"
        assert artifact2.value == "Content 2"

    async def test_artifact_with_complex_summary(self, event_bus, mock_agent):
        """Test Artifact with complex summary text."""
        response_text = '`Artifact[$complex, "Analysis: User Growth (2020-2024) - Key Findings", """Full report content"""]`'

        line = await LLMResponseLine.create(response_text, event_bus, mock_agent)

        assert "$complex" in line.vars
        artifact = line.vars["$complex"].value
        assert isinstance(artifact, Artifact)
        assert artifact.summary == "Analysis: User Growth (2020-2024) - Key Findings"
        assert artifact.value == "Full report content"
