"""Tests for InterpreterPrompt class."""

import types
from unittest.mock import MagicMock, Mock

import pytest

from playbooks.execution.interpreter_prompt import InterpreterPrompt, SetEncoder
from playbooks.infrastructure.event_bus import EventBus
from playbooks.state.call_stack import CallStack, CallStackFrame, InstructionPointer
from playbooks.state.variables import PlaybookDotMap


class MockNamespaceManager:
    """Mock namespace manager for testing."""

    def __init__(self, namespace=None):
        self.namespace = namespace or {}


class MockAgent:
    """Mock agent for testing."""

    def __init__(self, state=None, namespace=None, call_stack=None):
        self.id = "test_agent"
        self.klass = "TestAgent"
        self.state = state or PlaybookDotMap()
        self.namespace_manager = MockNamespaceManager(namespace or {})

        # Set up call stack
        if call_stack:
            self.call_stack = call_stack
        else:
            event_bus = EventBus("test-session")
            self.call_stack = CallStack(event_bus)
            # Push a dummy frame
            instruction_pointer = InstructionPointer(
                playbook="TestPlaybook",
                line_number="01",
                source_line_number=1,
            )
            frame = CallStackFrame(instruction_pointer=instruction_pointer)
            self.call_stack.push(frame)

    def to_dict(self):
        """Convert agent to dict representation."""
        return {
            "call_stack": [],
            "agents": [],
            "owned_meetings": [],
            "joined_meetings": [],
        }


@pytest.fixture
def mock_agent():
    """Fixture to create a mock agent."""
    return MockAgent()


@pytest.fixture
def interpreter_prompt(mock_agent):
    """Fixture to create an InterpreterPrompt instance."""
    return InterpreterPrompt(
        agent=mock_agent,
        playbooks={},
        current_playbook=None,
        instruction="Test instruction",
        agent_instructions="Test agent instructions",
        artifacts_to_load=[],
        trigger_instructions=[],
        agent_information="Test agent info",
        other_agent_klasses_information=[],
        execution_id=1,
    )


class TestSetEncoder:
    """Test suite for SetEncoder."""

    def test_encode_set(self):
        """Test encoding a set to list."""
        encoder = SetEncoder()
        result = encoder.default({1, 2, 3})
        assert isinstance(result, list)
        assert set(result) == {1, 2, 3}

    def test_encode_ellipsis(self):
        """Test encoding Ellipsis."""
        encoder = SetEncoder()
        result = encoder.default(Ellipsis)
        assert result == "..."

    def test_encode_module(self):
        """Test encoding a module."""
        encoder = SetEncoder()
        import json

        result = encoder.default(json)
        assert result == "<module: json>"

    def test_encode_class(self):
        """Test encoding a class."""
        encoder = SetEncoder()
        result = encoder.default(int)
        assert result == "<class: int>"

    def test_encode_unknown_object(self):
        """Test encoding an unknown object."""
        encoder = SetEncoder()

        class CustomClass:
            def __str__(self):
                return "custom_object"

        obj = CustomClass()
        result = encoder.default(obj)
        assert result.startswith("<CustomClass:")
        assert "custom_object" in result


class TestInterpreterPromptHelpers:
    """Test suite for InterpreterPrompt helper methods."""

    def test_is_literal_int(self, interpreter_prompt):
        """Test _is_literal with int."""
        assert interpreter_prompt._is_literal(42) is True

    def test_is_literal_float(self, interpreter_prompt):
        """Test _is_literal with float."""
        assert interpreter_prompt._is_literal(3.14) is True

    def test_is_literal_bool(self, interpreter_prompt):
        """Test _is_literal with bool."""
        assert interpreter_prompt._is_literal(True) is True
        assert interpreter_prompt._is_literal(False) is True

    def test_is_literal_none(self, interpreter_prompt):
        """Test _is_literal with None."""
        assert interpreter_prompt._is_literal(None) is True

    def test_is_literal_short_string(self, interpreter_prompt):
        """Test _is_literal with short string."""
        assert interpreter_prompt._is_literal("Hello World") is True

    def test_is_literal_long_string(self, interpreter_prompt):
        """Test _is_literal with long string (>200 chars)."""
        long_string = "a" * 201
        assert interpreter_prompt._is_literal(long_string) is False

    def test_is_literal_short_list(self, interpreter_prompt):
        """Test _is_literal with short list."""
        assert interpreter_prompt._is_literal([1, 2, 3]) is True

    def test_is_literal_long_list(self, interpreter_prompt):
        """Test _is_literal with long list."""
        # Create a list with repr > 100 chars
        long_list = list(range(50))
        assert interpreter_prompt._is_literal(long_list) is False

    def test_is_literal_short_dict(self, interpreter_prompt):
        """Test _is_literal with short dict."""
        assert interpreter_prompt._is_literal({"a": 1, "b": 2}) is True

    def test_is_literal_long_dict(self, interpreter_prompt):
        """Test _is_literal with long dict."""
        # Create a dict with repr > 100 chars
        long_dict = {f"key_{i}": i for i in range(20)}
        assert interpreter_prompt._is_literal(long_dict) is False

    def test_is_literal_object(self, interpreter_prompt):
        """Test _is_literal with custom object."""

        class CustomObject:
            pass

        obj = CustomObject()
        assert interpreter_prompt._is_literal(obj) is False

    def test_get_type_hint_agent_instance(self, interpreter_prompt):
        """Test _get_type_hint with agent-like object."""
        mock_agent = Mock()
        mock_agent.id = "agent_123"
        mock_agent.klass = "TestAgent"

        result = interpreter_prompt._get_type_hint(mock_agent)
        assert result == "TestAgent instance"

    def test_get_type_hint_regular_object(self, interpreter_prompt):
        """Test _get_type_hint with regular object."""
        result = interpreter_prompt._get_type_hint([1, 2, 3])
        assert result == "list"

    def test_get_type_hint_custom_class(self, interpreter_prompt):
        """Test _get_type_hint with custom class."""

        class MyClass:
            pass

        obj = MyClass()
        result = interpreter_prompt._get_type_hint(obj)
        assert result == "MyClass"

    def test_format_variable_literal_int(self, interpreter_prompt):
        """Test _format_variable with literal int."""
        result = interpreter_prompt._format_variable("count", 42)
        assert result == "count = 42"

    def test_format_variable_literal_string(self, interpreter_prompt):
        """Test _format_variable with literal string."""
        result = interpreter_prompt._format_variable("name", "Alice")
        assert result == "name = 'Alice'"

    def test_format_variable_literal_list(self, interpreter_prompt):
        """Test _format_variable with literal list."""
        result = interpreter_prompt._format_variable("items", [1, 2, 3])
        assert result == "items = [1, 2, 3]"

    def test_format_variable_non_literal(self, interpreter_prompt):
        """Test _format_variable with non-literal object."""

        class CustomClass:
            pass

        obj = CustomClass()
        result = interpreter_prompt._format_variable("obj", obj)
        assert result == "obj = ...  # CustomClass"

    def test_format_variable_agent_instance(self, interpreter_prompt):
        """Test _format_variable with agent instance."""
        mock_agent = Mock()
        mock_agent.id = "agent_456"
        mock_agent.klass = "WorkerAgent"

        result = interpreter_prompt._format_variable("worker", mock_agent)
        assert result == "worker = ...  # WorkerAgent instance"

    def test_format_state_dict_with_literals(self, interpreter_prompt):
        """Test _format_state_dict with literal values."""
        state = {
            "count": 10,
            "name": "Test",
            "active": True,
        }
        result = interpreter_prompt._format_state_dict(state)

        # Should be valid JSON with literal values
        import json

        parsed = json.loads(result)
        assert parsed["count"] == 10
        assert parsed["name"] == "Test"
        assert parsed["active"] is True

    def test_format_state_dict_with_non_literals(self, interpreter_prompt):
        """Test _format_state_dict with non-literal values."""

        class CustomObj:
            pass

        state = {
            "obj": CustomObj(),
            "count": 5,
        }
        result = interpreter_prompt._format_state_dict(state)

        import json

        parsed = json.loads(result)
        assert parsed["count"] == 5
        assert parsed["obj"] == "<CustomObj>"

    def test_format_state_dict_with_artifacts(self, interpreter_prompt):
        """Test _format_state_dict preserves artifact notation."""
        state = {
            "report": "Artifact: Sales report for Q4",
            "count": 42,
        }
        result = interpreter_prompt._format_state_dict(state)

        import json

        parsed = json.loads(result)
        assert parsed["report"] == "Artifact: Sales report for Q4"
        assert parsed["count"] == 42

    def test_format_state_dict_skips_internal_keys(self, interpreter_prompt):
        """Test _format_state_dict skips keys starting with underscore."""
        state = {
            "public": "value",
            "_internal": "hidden",
            "__private": "secret",
        }
        result = interpreter_prompt._format_state_dict(state)

        import json

        parsed = json.loads(result)
        assert "public" in parsed
        assert "_internal" not in parsed
        assert "__private" not in parsed

    def test_format_state_dict_with_mixed_types(self, interpreter_prompt):
        """Test _format_state_dict with mixed value types."""
        state = {
            "number": 100,
            "text": "short string",
            "long_text": "x" * 250,  # Non-literal
            "list": [1, 2],
            "artifact": "Artifact: Document content",
        }
        result = interpreter_prompt._format_state_dict(state)

        import json

        parsed = json.loads(result)
        assert parsed["number"] == 100
        assert parsed["text"] == "short string"
        assert parsed["long_text"] == "<str>"
        assert parsed["list"] == [1, 2]
        assert parsed["artifact"] == "Artifact: Document content"

    def test_extract_imports_empty_namespace(self, interpreter_prompt):
        """Test _extract_imports with empty namespace."""
        result = interpreter_prompt._extract_imports()
        assert result == []

    def test_extract_imports_with_modules(self):
        """Test _extract_imports with modules in namespace."""
        import json
        import os

        namespace = {
            "json": json,
            "os": os,
        }
        agent = MockAgent(namespace=namespace)
        prompt = InterpreterPrompt(
            agent=agent,
            playbooks={},
            current_playbook=None,
            instruction="Test",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="",
            other_agent_klasses_information=[],
        )

        result = prompt._extract_imports()
        assert "import json" in result
        assert "import os" in result
        assert len(result) == 2

    def test_extract_imports_with_alias(self):
        """Test _extract_imports with aliased modules."""

        # Create a mock module with different __name__
        mock_module = types.ModuleType("original_name")

        namespace = {
            "alias": mock_module,
        }
        agent = MockAgent(namespace=namespace)
        prompt = InterpreterPrompt(
            agent=agent,
            playbooks={},
            current_playbook=None,
            instruction="Test",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="",
            other_agent_klasses_information=[],
        )

        result = prompt._extract_imports()
        assert "import original_name as alias" in result

    def test_extract_imports_skips_private(self):
        """Test _extract_imports skips private imports (starting with _)."""
        import json

        namespace = {
            "json": json,
            "_private": json,
            "__very_private": json,
        }
        agent = MockAgent(namespace=namespace)
        prompt = InterpreterPrompt(
            agent=agent,
            playbooks={},
            current_playbook=None,
            instruction="Test",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="",
            other_agent_klasses_information=[],
        )

        result = prompt._extract_imports()
        assert "import json" in result
        assert len(result) == 1  # Only json, not private ones

    def test_extract_imports_sorted(self):
        """Test _extract_imports returns sorted results."""
        import json
        import os
        import sys

        namespace = {
            "sys": sys,
            "json": json,
            "os": os,
        }
        agent = MockAgent(namespace=namespace)
        prompt = InterpreterPrompt(
            agent=agent,
            playbooks={},
            current_playbook=None,
            instruction="Test",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="",
            other_agent_klasses_information=[],
        )

        result = prompt._extract_imports()
        assert result == sorted(result)


class TestBuildContextPrefix:
    """Test suite for _build_context_prefix method."""

    def test_basic_context_prefix_structure(self, interpreter_prompt):
        """Test basic structure of context prefix."""
        result = interpreter_prompt._build_context_prefix()

        # Should start and end with python code block markers
        assert result.startswith("```python\n")
        assert "```" in result

        # Should include call_stack
        assert "call_stack = " in result

        # Should include agents references
        assert "agents.by_klass" in result
        assert "agents.by_id" in result
        assert "agents.all" in result

        # Should include meetings
        assert "owned_meetings" in result
        assert "joined_meetings" in result

        # Should include self reference
        assert "self = ..." in result
        assert "TestAgent" in result

    def test_context_prefix_with_imports(self):
        """Test context prefix includes imports."""
        import json
        import os

        namespace = {
            "json": json,
            "os": os,
        }
        agent = MockAgent(namespace=namespace)
        prompt = InterpreterPrompt(
            agent=agent,
            playbooks={},
            current_playbook=None,
            instruction="Test",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="",
            other_agent_klasses_information=[],
        )

        result = prompt._build_context_prefix()
        assert "import json" in result
        assert "import os" in result

    def test_context_prefix_with_state_variables(self):
        """Test context prefix includes state variables."""
        agent = MockAgent()
        agent.state.count = 42
        agent.state.name = "Alice"
        agent.state.active = True

        prompt = InterpreterPrompt(
            agent=agent,
            playbooks={},
            current_playbook=None,
            instruction="Test",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="",
            other_agent_klasses_information=[],
        )

        result = prompt._build_context_prefix()
        assert "self.state.count = 42" in result
        assert "self.state.name = 'Alice'" in result
        assert "self.state.active = True" in result

    def test_context_prefix_with_local_variables(self):
        """Test context prefix includes local variables from frame."""
        event_bus = EventBus("test-session")
        call_stack = CallStack(event_bus)
        instruction_pointer = InstructionPointer(
            playbook="TestPlaybook",
            line_number="01",
            source_line_number=1,
        )
        frame = CallStackFrame(instruction_pointer=instruction_pointer)
        frame.locals = {
            "order_id": "12345",
            "customer_name": "Bob",
            "total": 99.99,
        }
        call_stack.push(frame)

        agent = MockAgent(call_stack=call_stack)
        prompt = InterpreterPrompt(
            agent=agent,
            playbooks={},
            current_playbook=None,
            instruction="Test",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="",
            other_agent_klasses_information=[],
        )

        result = prompt._build_context_prefix()
        assert "order_id = '12345'" in result
        assert "customer_name = 'Bob'" in result
        assert "total = 99.99" in result

    def test_context_prefix_skips_busy_state(self):
        """Test context prefix skips _busy internal state."""
        agent = MockAgent()
        agent.state.count = 10
        agent.state._busy = True

        prompt = InterpreterPrompt(
            agent=agent,
            playbooks={},
            current_playbook=None,
            instruction="Test",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="",
            other_agent_klasses_information=[],
        )

        result = prompt._build_context_prefix()
        assert "self.state.count = 10" in result
        assert "_busy" not in result

    def test_context_prefix_with_non_literal_state(self):
        """Test context prefix handles non-literal state values."""
        agent = MockAgent()
        agent.state.count = 5

        class CustomObject:
            pass

        agent.state.obj = CustomObject()

        prompt = InterpreterPrompt(
            agent=agent,
            playbooks={},
            current_playbook=None,
            instruction="Test",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="",
            other_agent_klasses_information=[],
        )

        result = prompt._build_context_prefix()
        assert "self.state.count = 5" in result
        assert "self.state.obj = ...  # CustomObject" in result

    def test_context_prefix_with_agent_dict_structure(self):
        """Test context prefix includes agent dictionary structure."""
        agent = MockAgent()

        def mock_to_dict():
            return {
                "call_stack": ["Playbook1:01", "Playbook2:05"],
                "agents": ["agent_1", "agent_2"],
                "owned_meetings": ["meeting_1"],
                "joined_meetings": ["meeting_2", "meeting_3"],
            }

        agent.to_dict = mock_to_dict

        prompt = InterpreterPrompt(
            agent=agent,
            playbooks={},
            current_playbook=None,
            instruction="Test",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="",
            other_agent_klasses_information=[],
        )

        result = prompt._build_context_prefix()
        assert "call_stack = ['Playbook1:01', 'Playbook2:05']" in result
        assert "agents.all = ['agent_1', 'agent_2']" in result
        assert "owned_meetings = ['meeting_1']" in result
        assert "joined_meetings = ['meeting_2', 'meeting_3']" in result

    def test_context_prefix_ends_with_double_newline(self, interpreter_prompt):
        """Test context prefix ends with proper formatting."""
        result = interpreter_prompt._build_context_prefix()
        # Should end with code block close and double newline
        assert result.endswith("```\n\n")


class TestAddArtifactHints:
    """Test suite for _add_artifact_hints method."""

    def test_add_artifact_hints_no_variables(self, interpreter_prompt):
        """Test _add_artifact_hints with no variables."""
        state_json = '{"data": "value"}'
        state_dict = {"data": "value"}

        result = interpreter_prompt._add_artifact_hints(state_json, state_dict)
        assert result == state_json

    def test_add_artifact_hints_non_artifact_variables(self, interpreter_prompt):
        """Test _add_artifact_hints with non-artifact variables."""
        state_json = '{\n  "variables": {\n    "count": 10,\n    "name": "test"\n  }\n}'
        state_dict = {
            "variables": {
                "count": 10,
                "name": "test",
            }
        }

        result = interpreter_prompt._add_artifact_hints(state_json, state_dict)
        # Should not add any hints for non-artifact variables
        assert "// content loaded" not in result
        assert "// not loaded" not in result

    def test_add_artifact_hints_loaded_artifact(self, interpreter_prompt):
        """Test _add_artifact_hints with loaded artifact."""
        # Mock the call stack to indicate artifact is loaded
        interpreter_prompt.agent.call_stack.is_artifact_loaded = MagicMock(
            return_value=True
        )

        state_json = (
            '{\n  "variables": {\n    "report": "Artifact: Sales report"\n  }\n}'
        )
        state_dict = {
            "variables": {
                "report": "Artifact: Sales report",
            }
        }

        result = interpreter_prompt._add_artifact_hints(state_json, state_dict)
        assert "// content loaded above" in result

    def test_add_artifact_hints_not_loaded_artifact(self, interpreter_prompt):
        """Test _add_artifact_hints with not loaded artifact."""
        # Mock the call stack to indicate artifact is not loaded
        interpreter_prompt.agent.call_stack.is_artifact_loaded = MagicMock(
            return_value=False
        )

        state_json = (
            '{\n  "variables": {\n    "document": "Artifact: User manual"\n  }\n}'
        )
        state_dict = {
            "variables": {
                "document": "Artifact: User manual",
            }
        }

        result = interpreter_prompt._add_artifact_hints(state_json, state_dict)
        assert "// not loaded: use LoadArtifact('document') to load" in result

    def test_add_artifact_hints_preserves_commas(self, interpreter_prompt):
        """Test _add_artifact_hints preserves trailing commas."""
        interpreter_prompt.agent.call_stack.is_artifact_loaded = MagicMock(
            return_value=True
        )

        state_json = '{\n  "variables": {\n    "report": "Artifact: Report",\n    "count": 5\n  }\n}'
        state_dict = {
            "variables": {
                "report": "Artifact: Report",
                "count": 5,
            }
        }

        result = interpreter_prompt._add_artifact_hints(state_json, state_dict)
        # Should preserve the comma after the hint
        assert (
            "// content loaded above," in result
            or "// content loaded above\n" in result
        )

    def test_add_artifact_hints_multiple_artifacts(self, interpreter_prompt):
        """Test _add_artifact_hints with multiple artifacts."""

        def mock_is_loaded(name):
            return name == "doc1"  # Only doc1 is loaded

        interpreter_prompt.agent.call_stack.is_artifact_loaded = mock_is_loaded

        state_json = '{\n  "variables": {\n    "doc1": "Artifact: First doc",\n    "doc2": "Artifact: Second doc"\n  }\n}'
        state_dict = {
            "variables": {
                "doc1": "Artifact: First doc",
                "doc2": "Artifact: Second doc",
            }
        }

        result = interpreter_prompt._add_artifact_hints(state_json, state_dict)
        assert "// content loaded above" in result
        assert "// not loaded: use LoadArtifact('doc2') to load" in result


class TestContextPrefixLocalVariables:
    """Test suite for local variables in context prefix."""

    def test_context_shows_simple_locals(self):
        """Test that simple local variables are displayed in context prefix."""
        event_bus = EventBus("test-session")
        call_stack = CallStack(event_bus)
        instruction_pointer = InstructionPointer(
            playbook="TestPlaybook",
            line_number="01",
            source_line_number=1,
        )
        frame = CallStackFrame(instruction_pointer=instruction_pointer)
        frame.locals = {
            "count": 42,
            "message": "Hello",
            "active": True,
        }
        call_stack.push(frame)

        agent = MockAgent(call_stack=call_stack)
        prompt = InterpreterPrompt(
            agent=agent,
            playbooks={},
            current_playbook=None,
            instruction="Test",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="",
            other_agent_klasses_information=[],
        )

        result = prompt._build_context_prefix()

        # Verify local variables are shown
        assert "count = 42" in result
        assert "message = 'Hello'" in result
        assert "active = True" in result

    def test_context_shows_locals_and_state(self):
        """Test that both local and state variables are displayed correctly."""
        event_bus = EventBus("test-session")
        call_stack = CallStack(event_bus)
        instruction_pointer = InstructionPointer(
            playbook="TestPlaybook",
            line_number="01",
            source_line_number=1,
        )
        frame = CallStackFrame(instruction_pointer=instruction_pointer)
        frame.locals = {
            "local_var": 100,
            "name": "Alice",
        }
        call_stack.push(frame)

        agent = MockAgent(call_stack=call_stack)
        agent.state.state_var = 200
        agent.state.status = "active"

        prompt = InterpreterPrompt(
            agent=agent,
            playbooks={},
            current_playbook=None,
            instruction="Test",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="",
            other_agent_klasses_information=[],
        )

        result = prompt._build_context_prefix()

        # Verify local variables (not prefixed with self.state)
        assert "local_var = 100" in result
        assert "name = 'Alice'" in result

        # Verify state variables (prefixed with self.state)
        assert "self.state.state_var = 200" in result
        assert "self.state.status = 'active'" in result

    def test_context_shows_playbook_args_as_locals(self):
        """Test that playbook arguments appear as local variables in context."""
        event_bus = EventBus("test-session")
        call_stack = CallStack(event_bus)
        instruction_pointer = InstructionPointer(
            playbook="TestPlaybook",
            line_number="01",
            source_line_number=1,
        )
        frame = CallStackFrame(instruction_pointer=instruction_pointer)
        # Playbook args are stored in frame.locals
        frame.locals = {
            "order_id": "12345",
            "customer_name": "John Doe",
            "total": 99.99,
        }
        call_stack.push(frame)

        agent = MockAgent(call_stack=call_stack)
        prompt = InterpreterPrompt(
            agent=agent,
            playbooks={},
            current_playbook=None,
            instruction="Test",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="",
            other_agent_klasses_information=[],
        )

        result = prompt._build_context_prefix()

        # Playbook args should appear as regular local variables
        assert "order_id = '12345'" in result
        assert "customer_name = 'John Doe'" in result
        assert "total = 99.99" in result

    def test_context_locals_formatting(self):
        """Test that local variables are formatted correctly (literal vs non-literal)."""
        event_bus = EventBus("test-session")
        call_stack = CallStack(event_bus)
        instruction_pointer = InstructionPointer(
            playbook="TestPlaybook",
            line_number="01",
            source_line_number=1,
        )
        frame = CallStackFrame(instruction_pointer=instruction_pointer)

        # Create a custom object for non-literal test
        class CustomObject:
            pass

        frame.locals = {
            "simple_int": 42,
            "simple_str": "test",
            "simple_list": [1, 2, 3],
            "custom_obj": CustomObject(),
            "long_string": "x" * 250,  # Too long to be literal
        }
        call_stack.push(frame)

        agent = MockAgent(call_stack=call_stack)
        prompt = InterpreterPrompt(
            agent=agent,
            playbooks={},
            current_playbook=None,
            instruction="Test",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="",
            other_agent_klasses_information=[],
        )

        result = prompt._build_context_prefix()

        # Literals should show actual values
        assert "simple_int = 42" in result
        assert "simple_str = 'test'" in result
        assert "simple_list = [1, 2, 3]" in result

        # Non-literals should show type hints with ...
        assert "custom_obj = ...  # CustomObject" in result
        assert "long_string = ...  # str" in result

    def test_context_empty_frame_no_locals(self):
        """Test that context handles frames with no locals gracefully."""
        event_bus = EventBus("test-session")
        call_stack = CallStack(event_bus)
        instruction_pointer = InstructionPointer(
            playbook="TestPlaybook",
            line_number="01",
            source_line_number=1,
        )
        frame = CallStackFrame(instruction_pointer=instruction_pointer)
        # Empty locals dict
        frame.locals = {}
        call_stack.push(frame)

        agent = MockAgent(call_stack=call_stack)
        prompt = InterpreterPrompt(
            agent=agent,
            playbooks={},
            current_playbook=None,
            instruction="Test",
            agent_instructions="",
            artifacts_to_load=[],
            trigger_instructions=[],
            agent_information="",
            other_agent_klasses_information=[],
        )

        result = prompt._build_context_prefix()

        # Should still produce valid context, just without local variables
        assert "```python" in result
        assert "```" in result
        assert "self = ..." in result
        # Should not have any variable assignments before self
        lines = result.split("\n")
        found_self = False
        for line in lines:
            if "self = ..." in line:
                found_self = True
                break
            # Before self line, should only have imports, call_stack, agents, meetings
            if "=" in line and line.strip() and not line.strip().startswith("#"):
                assert any(
                    keyword in line
                    for keyword in [
                        "call_stack",
                        "owned_meetings",
                        "joined_meetings",
                        "agents",
                        "import",
                    ]
                )
        assert found_self
