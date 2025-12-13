import pytest

from playbooks.execution.streaming_python_executor import StreamingPythonExecutor
from playbooks.infrastructure.event_bus import EventBus
from playbooks.state.call_stack import CallStack, CallStackFrame, InstructionPointer
from playbooks.state.variables import PlaybookDotMap


class _MockProgram:
    def __init__(self):
        self._debug_server = None


class _MockAgent:
    """Minimal agent stub for StreamingPythonExecutor tests."""

    def __init__(self):
        self.id = "test_agent"
        self.klass = "MockAgent"
        event_bus = EventBus("test-session")
        self._variables_internal = PlaybookDotMap()
        self.call_stack = CallStack(event_bus)
        self.program = _MockProgram()
        self.playbooks = {}
        self.namespace_manager = None

        # Runtime internals that should not be mutated by streamed code
        self.joined_meetings = {"100": object()}
        self.owned_meetings = {"200": object()}

        ip = InstructionPointer(
            playbook="TestPlaybook", line_number="00", source_line_number=0
        )
        self.call_stack.push(CallStackFrame(instruction_pointer=ip))

    @property
    def state(self):
        return self._variables_internal

    def parse_instruction_pointer(self, step: str):
        parts = step.split(":")
        return InstructionPointer(
            playbook=parts[0] if len(parts) > 0 else "",
            line_number=parts[1] if len(parts) > 1 else "",
            source_line_number=0,
            step=parts[2] if len(parts) > 2 else None,
        )

    def resolve_target(self, target: str, allow_fallback: bool = True) -> str:
        return target

    @property
    def _current_executor(self):
        current_frame = self.call_stack.peek()
        if not current_frame or not getattr(current_frame, "executor", None):
            raise RuntimeError("Called outside of code execution context")
        return current_frame.executor

    async def Step(self, location: str):
        await self._current_executor.capture_step(location)


@pytest.mark.asyncio
async def test_streaming_executor_skips_bare_identifier_expression():
    agent = _MockAgent()
    executor = StreamingPythonExecutor(agent)

    # A standalone identifier (e.g. leaked from markdown fences) should not crash.
    await executor.add_chunk("python\n")
    result = await executor.finalize()
    assert result.error_message is None


@pytest.mark.asyncio
async def test_streaming_executor_blocks_assignment_to_joined_meetings():
    agent = _MockAgent()
    executor = StreamingPythonExecutor(agent)

    await executor.add_chunk("self.joined_meetings = []\n")
    result = await executor.finalize()

    assert result.error_message is None
    assert isinstance(agent.joined_meetings, dict)
    assert "100" in agent.joined_meetings


@pytest.mark.asyncio
async def test_streaming_executor_skips_state_list_like_append_calls():
    agent = _MockAgent()
    executor = StreamingPythonExecutor(agent)

    # Simulate an LLM trying to treat a state field as a list.
    await executor.add_chunk("if not hasattr(self.state, 'evaluation_results'):\n")
    await executor.add_chunk("    self.state.evaluation_results = []\n")
    await executor.add_chunk("self.state.evaluation_results.append({'x': 1})\n")
    result = await executor.finalize()

    # Should not crash even if evaluation_results isn't actually a list-compatible object.
    assert result.error_message is None


@pytest.mark.asyncio
async def test_streaming_executor_blocks_read_of_joined_meetings():
    agent = _MockAgent()
    executor = StreamingPythonExecutor(agent)

    # LLM sometimes introspects internal meeting state incorrectly; this should be skipped.
    await executor.add_chunk("x = [m['meeting_id'] for m in self.joined_meetings]\n")
    result = await executor.finalize()
    assert result.error_message is None
