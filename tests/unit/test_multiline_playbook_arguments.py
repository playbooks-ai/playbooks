"""Tests for multi-line string arguments in playbook calls."""

import pytest

from playbooks.argument_types import LiteralValue, VariableReference
from playbooks.event_bus import EventBus
from playbooks.llm_response import LLMResponse
from playbooks.llm_response_line import LLMResponseLine
from playbooks.variables import Artifact


class MockAgent:
    """Mock agent for testing."""

    def __init__(self):
        self.id = "test_agent"
        self.state = MockState()

    def parse_instruction_pointer(self, step: str):
        """Mock parse_instruction_pointer method."""
        parts = step.split(":")
        return {
            "playbook": parts[0] if len(parts) > 0 else "",
            "line": parts[1] if len(parts) > 1 else "",
            "step": parts[2] if len(parts) > 2 else "",
            "type": parts[3] if len(parts) > 3 else "",
        }


class MockState:
    """Mock state for testing."""

    def __init__(self):
        self.last_llm_response = None


@pytest.fixture
def event_bus():
    """Fixture to create an EventBus instance."""
    return EventBus("test-session")


@pytest.fixture
def mock_agent():
    """Fixture to create a mock agent."""
    return MockAgent()


@pytest.mark.asyncio
class TestMultiLinePlaybookArguments:
    """Test suite for multi-line string arguments in playbook calls."""

    async def test_simple_multiline_string(self, event_bus, mock_agent):
        """Test parsing playbook call with simple multi-line string."""
        line = await LLMResponseLine.create(
            '`Say("user", """Hello\nWorld\nMultiline""")` Greeting user',
            event_bus,
            mock_agent,
        )
        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.playbook_klass == "Say"
        assert len(call.args) == 2
        assert isinstance(call.args[0], LiteralValue)
        assert call.args[0].value == "user"
        assert isinstance(call.args[1], LiteralValue)
        assert call.args[1].value == "Hello\nWorld\nMultiline"

    async def test_multiline_string_with_embedded_quotes(self, event_bus, mock_agent):
        """Test parsing playbook call with multi-line string containing quotes."""
        line = await LLMResponseLine.create(
            '`Say("user", """Hello "friend"\nHow are you?""")` Greeting',
            event_bus,
            mock_agent,
        )
        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.playbook_klass == "Say"
        assert call.args[1].value == 'Hello "friend"\nHow are you?'

    async def test_multiline_string_with_variable_assignment(
        self, event_bus, mock_agent
    ):
        """Test parsing playbook call with variable assignment and multi-line string."""
        line = await LLMResponseLine.create(
            '`$result:str = Format("""Line 1\nLine 2\nLine 3""")` Formatting text',
            event_bus,
            mock_agent,
        )
        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.variable_to_assign == "$result"
        assert call.type_annotation == "str"
        assert call.playbook_klass == "Format"
        assert len(call.args) == 1
        assert call.args[0].value == "Line 1\nLine 2\nLine 3"

    async def test_multiple_multiline_calls_on_same_line(self, event_bus, mock_agent):
        """Test parsing multiple playbook calls with multi-line strings on same line."""
        # Note: This would be unusual in practice, but should work
        text = '`Say("user", """Hello\nWorld""")` and `Log("""Debug\nInfo""")`'
        line = await LLMResponseLine.create(text, event_bus, mock_agent)
        assert len(line.playbook_calls) == 2
        assert line.playbook_calls[0].playbook_klass == "Say"
        assert line.playbook_calls[0].args[1].value == "Hello\nWorld"
        assert line.playbook_calls[1].playbook_klass == "Log"
        assert line.playbook_calls[1].args[0].value == "Debug\nInfo"

    async def test_multiline_string_with_kwargs(self, event_bus, mock_agent):
        """Test parsing playbook call with keyword argument containing multi-line string."""
        line = await LLMResponseLine.create(
            '`SendEmail(recipient="user@example.com", body="""Dear user,\n\nThank you!\n\nBest regards""")` Sending email',
            event_bus,
            mock_agent,
        )
        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.playbook_klass == "SendEmail"
        assert call.kwargs["recipient"].value == "user@example.com"
        assert call.kwargs["body"].value == "Dear user,\n\nThank you!\n\nBest regards"

    async def test_mixed_singleline_and_multiline_args(self, event_bus, mock_agent):
        """Test parsing playbook call with both single-line and multi-line string arguments."""
        line = await LLMResponseLine.create(
            '`CreateDocument("report", """Title: Annual Report\n\nContent:\n- Item 1\n- Item 2""")` Creating document',
            event_bus,
            mock_agent,
        )
        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.playbook_klass == "CreateDocument"
        assert len(call.args) == 2
        assert call.args[0].value == "report"
        assert (
            call.args[1].value == "Title: Annual Report\n\nContent:\n- Item 1\n- Item 2"
        )

    async def test_multiline_string_with_variable_reference(
        self, event_bus, mock_agent
    ):
        """Test parsing playbook call with multi-line string and variable reference."""
        line = await LLMResponseLine.create(
            '`Process($data, template="""Header: {title}\n\nBody:\n{content}""")` Processing',
            event_bus,
            mock_agent,
        )
        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.playbook_klass == "Process"
        assert isinstance(call.args[0], VariableReference)
        assert call.args[0].reference == "$data"
        assert call.kwargs["template"].value == "Header: {title}\n\nBody:\n{content}"

    async def test_llm_response_with_multiline_call(self, event_bus, mock_agent):
        """Test that LLMResponse correctly handles multi-line playbook calls."""
        response_text = 'plan - greet user\n`Step["Greet:01:QUE"]` `Say("user", """Hello there!\nWelcome to our service.\nHow can I help you today?""")`\ntrig? no\nyld? no'

        response = await LLMResponse.create(response_text, event_bus, mock_agent)

        # Should be split into 4 lines (the multi-line Say call is kept together)
        assert len(response.lines) == 4

        # Find the line with the playbook call
        call_line = None
        for line in response.lines:
            if len(line.playbook_calls) > 0:
                call_line = line
                break

        assert call_line is not None
        assert len(call_line.playbook_calls) == 1
        call = call_line.playbook_calls[0]
        assert call.playbook_klass == "Say"
        assert (
            call.args[1].value
            == "Hello there!\nWelcome to our service.\nHow can I help you today?"
        )

    async def test_multiline_call_with_agent_prefix(self, event_bus, mock_agent):
        """Test parsing playbook call with agent prefix and multi-line string."""
        line = await LLMResponseLine.create(
            '`EmailAgent.Send(to="user@test.com", message="""Hi,\n\nUpdate here.\n\nThanks""")` Sending',
            event_bus,
            mock_agent,
        )
        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.playbook_klass == "EmailAgent.Send"
        assert call.kwargs["message"].value == "Hi,\n\nUpdate here.\n\nThanks"

    async def test_multiline_string_empty_lines(self, event_bus, mock_agent):
        """Test parsing playbook call with multi-line string containing empty lines."""
        line = await LLMResponseLine.create(
            '`Log("""Line 1\n\nLine 3\n\nLine 5""")` Logging with gaps',
            event_bus,
            mock_agent,
        )
        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.args[0].value == "Line 1\n\nLine 3\n\nLine 5"

    async def test_multiline_string_with_special_characters(
        self, event_bus, mock_agent
    ):
        """Test parsing playbook call with multi-line string containing special characters."""
        line = await LLMResponseLine.create(
            '`Format("""Symbol: $\nPercent: %\nBackslash: \\\nTab:\t""")` Formatting',
            event_bus,
            mock_agent,
        )
        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        # The string should preserve special characters
        assert "$" in call.args[0].value
        assert "%" in call.args[0].value

    async def test_artifact_and_multiline_call_together(self, event_bus, mock_agent):
        """Test parsing line with both artifact and multi-line playbook call."""
        # Use actual newlines in the artifact and playbook call
        response_text = '`Artifact[$report, "Summary", """Detailed report content"""]` `Say("user", """Here is your report:\nPlease review.""")`'

        line = await LLMResponseLine.create(response_text, event_bus, mock_agent)

        # Should have both the artifact and the playbook call
        assert "$report" in line.vars
        artifact = line.vars["$report"].value
        # Verify it's an Artifact object

        assert isinstance(artifact, Artifact)
        assert artifact.summary == "Summary"
        assert artifact.value == "Detailed report content"

        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.playbook_klass == "Say"
        assert call.args[1].value == "Here is your report:\nPlease review."

    async def test_var_with_triple_quotes_creates_string_not_artifact(
        self, event_bus, mock_agent
    ):
        """Test that Var with triple quotes creates a regular string, not an artifact."""
        response_text = '`Var[$address, """123 Main St\nApt 4B\nNew York, NY"""]`'

        line = await LLMResponseLine.create(response_text, event_bus, mock_agent)

        # Should have the variable
        assert "$address" in line.vars
        value = line.vars["$address"].value

        # Verify it's NOT an Artifact object - it should be a plain string
        assert not isinstance(value, Artifact)
        assert isinstance(value, str)
        assert value == "123 Main St\nApt 4B\nNew York, NY"

    async def test_full_llm_response_with_multiple_multiline_calls(
        self, event_bus, mock_agent
    ):
        """Test complete LLM response with multiple multi-line calls across different lines."""
        response_text = (
            "recap - processing user request\n"
            "plan - send greeting and instructions\n"
            '`Step["Process:01:QUE"]` `Say("user", """Welcome!\nThis is a multi-line greeting.\nWe\'re glad to help you.""")`\n'
            "trig? no\n"
            "yld? no\n"
            '`Step["Process:02:QUE"]` `SendEmail(subject="Instructions", body="""Dear user,\n\nHere are the next steps:\n1. Review the document\n2. Sign the form\n3. Submit the application\n\nThank you!""")`\n'
            "trig? no\n"
            "yld? yes, for call"
        )

        response = await LLMResponse.create(response_text, event_bus, mock_agent)

        # Count playbook calls across all lines
        total_calls = sum(len(line.playbook_calls) for line in response.lines)
        assert total_calls == 2

        # Verify first call
        say_call = None
        email_call = None
        for line in response.lines:
            for call in line.playbook_calls:
                if call.playbook_klass == "Say":
                    say_call = call
                elif call.playbook_klass == "SendEmail":
                    email_call = call

        assert say_call is not None
        assert "Welcome!" in say_call.args[1].value
        assert "multi-line greeting" in say_call.args[1].value

        assert email_call is not None
        assert email_call.kwargs["subject"].value == "Instructions"
        assert "Dear user" in email_call.kwargs["body"].value
        assert "Review the document" in email_call.kwargs["body"].value
        assert "Thank you!" in email_call.kwargs["body"].value
