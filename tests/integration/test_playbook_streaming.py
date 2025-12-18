"""Tests for streaming Say() handling in PlaybookLLMExecution."""

import pytest

import playbooks.execution.playbook as playbook_module
from playbooks.execution.playbook import PlaybookLLMExecution
from playbooks.infrastructure.event_bus import EventBus
from playbooks.state.call_stack import CallStack, CallStackFrame, InstructionPointer


class DummyStreamResult:
    """Simple stream result used for channel streaming stubs."""

    def __init__(self, stream_id: str = "stream-1", should_stream: bool = True):
        self.stream_id = stream_id
        self.should_stream = should_stream


class DummyPlaybook:
    """Minimal playbook placeholder."""

    def __init__(self, name: str = "TestPlaybook"):
        self.name = name


class DummyState:
    """Minimal agent state with call stack."""

    def __init__(self):
        self.event_bus = EventBus("test-session")
        self.call_stack = CallStack(self.event_bus, agent_id="test-agent")
        instruction_pointer = InstructionPointer(
            playbook="TestPlaybook",
            line_number="01",
            source_line_number=0,
        )
        self.call_stack.push(CallStackFrame(instruction_pointer))


class DummyAgent:
    """Agent stub capturing streaming calls."""

    def __init__(self):
        self.id = "test-agent"
        self.klass = "DummyAgent"
        self.state = DummyState()
        self.call_stack = self.state.call_stack  # Use call_stack from state
        self.event_bus = self.state.event_bus  # Add event_bus reference for telemetry
        self.program = type(
            "Program",
            (),
            {
                "enable_agent_streaming": False,
                "_debug_server": None,
                "event_bus": self.state.event_bus,
            },
        )()  # noqa: E501
        self.playbooks = {}
        self.description = "Test agent"
        self._currently_streaming = False
        self.stream_updates = []
        self.stream_completions = []

    async def start_streaming_say_via_channel(self, recipient: str):
        return DummyStreamResult()

    async def stream_say_update_via_channel(
        self, stream_id: str, recipient: str, content: str
    ):
        self.stream_updates.append(content)

    async def complete_streaming_say_via_channel(
        self, stream_id: str, recipient: str, content: str
    ):
        self.stream_completions.append(content)

    def other_agent_klasses_information(self):
        return []

    def all_trigger_instructions(self):
        return []

    def get_compact_information(self):
        return ""


class DummyPrompt:
    """Prompt stub with minimal messages interface."""

    def __init__(self, messages=None):
        self.messages = messages or []


class DummyStreamingExecutor:
    """Streaming executor stub that just collects chunks."""

    def __init__(self, agent, playbook_args, execution_id=None):
        self.agent = agent
        self.playbook_args = playbook_args
        self.execution_id = execution_id
        self.chunks = []
        self.result = "executed"

    async def add_chunk(self, chunk: str):
        self.chunks.append(chunk)

    async def finalize(self):
        return self.result


async def _run_stream(
    monkeypatch: pytest.MonkeyPatch, chunks, prompt: DummyPrompt = None
):
    """Helper to run _stream_llm_response with stubbed dependencies."""
    agent = DummyAgent()
    execution = PlaybookLLMExecution(agent, DummyPlaybook())
    prompt = prompt or DummyPrompt()

    # Patch streaming executor and LLM completion
    monkeypatch.setattr(
        playbook_module, "StreamingPythonExecutor", DummyStreamingExecutor
    )
    monkeypatch.setattr(
        playbook_module, "get_completion", lambda **kwargs: iter(chunks)
    )

    buffer = await execution._stream_llm_response(prompt)
    return agent, buffer, execution


@pytest.mark.asyncio
async def test_streams_single_quoted_say(monkeypatch):
    """Ensure streaming works for single-quoted Say content."""
    chunks = ['Say("human", "Hello there")']
    agent, buffer, execution = await _run_stream(monkeypatch, chunks)

    assert buffer == "".join(chunks)
    assert agent.stream_updates  # streamed at least once
    assert agent.stream_updates[-1] == "Hello there"
    assert agent.stream_completions[-1] == "Hello there"
    assert execution.streaming_execution_result == "executed"


@pytest.mark.asyncio
async def test_streams_triple_quoted_say(monkeypatch):
    """Ensure streaming works for triple-quoted Say content."""
    chunks = ['Say("human", """Hello\nWorld!""")']
    agent, buffer, execution = await _run_stream(monkeypatch, chunks)

    assert buffer == "".join(chunks)
    # Triple-quoted message should complete with content stripped of quotes
    assert agent.stream_completions[-1] == "Hello\nWorld!"
    assert execution.streaming_execution_result == "executed"


@pytest.mark.asyncio
async def test_streams_triple_quoted_say_split(monkeypatch):
    """Ensure streaming works for triple-quoted Say content."""
    chunks = ['Say("human", ', '"', '"', '"', "Hello\nWorld!", '""', '")']
    agent, buffer, execution = await _run_stream(monkeypatch, chunks)

    assert buffer == "".join(chunks)
    # Triple-quoted message should complete with content stripped of quotes
    assert agent.stream_completions[-1] == "Hello\nWorld!"
    assert execution.streaming_execution_result == "executed"
