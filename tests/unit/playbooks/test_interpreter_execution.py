"""Tests for the InterpreterExecution class."""

import contextlib
from unittest.mock import MagicMock, patch

import pytest

from playbooks.interpreter import InterpreterExecution
from playbooks.playbook_step import PlaybookStep, PlaybookStepCollection
from playbooks.types import AgentResponseChunk, ToolCall


@pytest.fixture
def mock_interpreter():
    """Create a mock interpreter for testing."""
    interpreter = MagicMock()
    interpreter.session_context.return_value = "Session context"
    interpreter.get_prompt.return_value = "Test prompt"
    interpreter.handle_empty_call_stack.return_value = (False, None)
    return interpreter


@pytest.fixture
def mock_playbooks():
    """Create mock playbooks for testing."""
    playbook = MagicMock()
    playbook.klass = "TestPlaybook"
    return {"TestPlaybook": playbook, "Say": playbook}


@pytest.fixture
def mock_current_playbook():
    """Create a mock current playbook for testing."""
    playbook = MagicMock()
    playbook.klass = "TestPlaybook"
    return playbook


class TestInterpreterExecution:
    """Tests for the InterpreterExecution class."""

    def test_initialization(
        self, mock_interpreter, mock_playbooks, mock_current_playbook
    ):
        """Test that the InterpreterExecution class initializes correctly."""
        instruction = "Test instruction"
        llm_config = {"model": "test-model"}
        stream = True

        interpreter_execution = InterpreterExecution(
            interpreter=mock_interpreter,
            playbooks=mock_playbooks,
            current_playbook=mock_current_playbook,
            instruction=instruction,
            llm_config=llm_config,
            stream=stream,
        )

        assert interpreter_execution.interpreter == mock_interpreter
        assert interpreter_execution.playbooks == mock_playbooks
        assert interpreter_execution.current_playbook == mock_current_playbook
        assert interpreter_execution.instruction == instruction
        assert interpreter_execution.llm_config == llm_config
        assert interpreter_execution.stream == stream
        assert interpreter_execution.wait_for_external_event is False
        assert hasattr(interpreter_execution, "_trace_items")

    def test_parse_response_json_block(self):
        """Test parsing a response with a JSON block."""
        interpreter_execution = InterpreterExecution(
            interpreter=MagicMock(),
            playbooks={"Say": MagicMock()},
            current_playbook=MagicMock(),
            instruction="Test instruction",
        )

        response = """
Here's the execution:

```json
[
  {
    "TestPlaybook:01:CMD": [
      {
        "call": {
          "fn": "Say",
          "args": [],
          "kwargs": {
            "message": "Hello, world!"
          }
        }
      },
      {
        "updated_vars": {
          "$greeting": "Hello, world!"
        }
      }
    ]
  }
]
```
"""

        (
            tool_calls,
            last_executed_step,
            updated_variables,
        ) = interpreter_execution.parse_response(response)

        assert len(tool_calls) == 1
        assert tool_calls[0].fn == "Say"
        assert tool_calls[0].args == []
        assert tool_calls[0].kwargs == {"message": "Hello, world!"}
        assert last_executed_step == "TestPlaybook:01:CMD"
        assert updated_variables == {"$greeting": "Hello, world!"}

    def test_parse_response_direct_json(self):
        """Test parsing a response with direct JSON content."""
        interpreter_execution = InterpreterExecution(
            interpreter=MagicMock(),
            playbooks={"Say": MagicMock()},
            current_playbook=MagicMock(),
            instruction="Test instruction",
        )

        response = """
[
  {
    "TestPlaybook:01:CMD": [
      {
        "call": {
          "fn": "Say",
          "args": [],
          "kwargs": {
            "message": "Hello, world!"
          }
        }
      },
      {
        "updated_vars": {
          "$greeting": "Hello, world!"
        }
      }
    ]
  }
]
"""

        (
            tool_calls,
            last_executed_step,
            updated_variables,
        ) = interpreter_execution.parse_response(response)

        assert len(tool_calls) == 1
        assert tool_calls[0].fn == "Say"
        assert tool_calls[0].args == []
        assert tool_calls[0].kwargs == {"message": "Hello, world!"}
        assert last_executed_step == "TestPlaybook:01:CMD"
        assert updated_variables == {"$greeting": "Hello, world!"}

    def test_parse_response_invalid_json(self):
        """Test parsing a response with invalid JSON content."""
        interpreter_execution = InterpreterExecution(
            interpreter=MagicMock(),
            playbooks={},
            current_playbook=MagicMock(),
            instruction="Test instruction",
        )

        response = "This is not valid JSON content."

        with pytest.raises(ValueError) as excinfo:
            interpreter_execution.parse_response(response)

        # The error message could be either "Empty JSON content" or "Invalid JSON content"
        assert "JSON content" in str(excinfo.value)

    @patch("playbooks.interpreter.interpreter_execution.get_messages_for_prompt")
    @patch("playbooks.interpreter.interpreter_execution.LLMCall")
    def test_execute(
        self,
        mock_llm_call_class,
        mock_get_messages,
        mock_interpreter,
        mock_playbooks,
        mock_current_playbook,
    ):
        """Test that the execute method works correctly."""
        # Set up the mocks
        mock_get_messages.return_value = ["Test message"]

        mock_llm_call = MagicMock()
        mock_llm_call.execute.return_value = ["Test response"]
        mock_llm_call_class.return_value = mock_llm_call

        # Set up the call stack mock to ensure handle_empty_call_stack returns False, None
        mock_call_stack = MagicMock()
        mock_call_stack.is_empty.return_value = False
        mock_call_stack.peek.return_value = MagicMock()
        mock_interpreter.call_stack = mock_call_stack
        mock_interpreter.handle_empty_call_stack.return_value = (False, None)
        mock_interpreter.get_current_playbook_name.return_value = (
            mock_current_playbook.klass
        )

        # Mock the parse_response method and _get_llm_response method
        with patch.object(
            InterpreterExecution, "parse_response"
        ) as mock_parse_response, patch.object(
            InterpreterExecution, "_get_llm_response"
        ) as mock_get_llm_response:
            mock_parse_response.return_value = (
                [
                    ToolCall(
                        fn="Say",
                        args=[],
                        kwargs={"message": "Hello", "waitForUserInput": True},
                    )
                ],
                "TestPlaybook:01:CMD",
                {"$greeting": "Hello"},
            )

            # Set up the _get_llm_response mock to yield a response chunk
            mock_get_llm_response.return_value = [
                AgentResponseChunk(raw="Test response")
            ]

            # Create the interpreter execution
            interpreter_execution = InterpreterExecution(
                interpreter=mock_interpreter,
                playbooks=mock_playbooks,
                current_playbook=mock_current_playbook,
                instruction="Test instruction",
                llm_config={"model": "test-model"},
                stream=True,
            )

            # Execute the interpreter
            result = list(interpreter_execution.execute())

            # Check that the methods were called with the correct arguments
            mock_get_llm_response.assert_called_once()
            mock_parse_response.assert_called_once()

            # Check that the wait_for_external_event flag was set correctly
            assert interpreter_execution.wait_for_external_event is True

            # Check that the result contains the expected chunks
            assert len(result) > 0

    def test_repr(self):
        """Test that the __repr__ method returns the expected string."""
        interpreter_execution = InterpreterExecution(
            interpreter=MagicMock(),
            playbooks={},
            current_playbook=MagicMock(),
            instruction="Test instruction",
        )

        # Add some trace items
        interpreter_execution.trace(
            "Start inner loop iteration",
            metadata={
                "playbook": "TestPlaybook",
                "line_number": "01",
                "instruction": "Test",
            },
        )
        interpreter_execution.trace(
            "Start iteration",
            metadata={
                "playbook": "TestPlaybook",
                "line_number": "02",
                "instruction": "Test",
            },
        )

        # The __repr__ method only includes "Start inner loop iteration" trace items
        assert repr(interpreter_execution) == "TestPlaybook:01"

    def test_update_call_stack_with_yld(self):
        """Test updating call stack with a YLD instruction."""
        interpreter = MagicMock()
        interpreter.call_stack.peek.return_value = None

        # Create a step collection with test steps
        step_collection = PlaybookStepCollection()
        step_collection.add_step(
            PlaybookStep("01", "YLD", "ForUserInput", "01:YLD: ForUserInput")
        )
        step_collection.add_step(
            PlaybookStep(
                "02", "QUE", "Say(message='Hello')", "02:QUE: Say(message='Hello')"
            )
        )
        step_collection.add_step(
            PlaybookStep("03", "RET", "return result", "03:RET: return result")
        )

        # Mock the current playbook with step collection
        current_playbook = MagicMock()
        current_playbook.get_step.side_effect = lambda ln: step_collection.get_step(ln)
        current_playbook.get_next_step.side_effect = (
            lambda ln: step_collection.get_next_step(ln)
        )

        interpreter_execution = InterpreterExecution(
            interpreter=interpreter,
            playbooks={},
            current_playbook=current_playbook,
            instruction="Test instruction",
        )

        # Test YLD instruction advances to the next line
        interpreter_execution._update_call_stack("TestPlaybook:01:YLD", [])

        # Verify the call stack was updated correctly
        assert interpreter.call_stack.pop.call_count == 1

        # Verify a new frame was pushed with the next line number
        assert interpreter.call_stack.push.call_count == 1
        call_args = interpreter.call_stack.push.call_args[0][0]
        assert call_args.instruction_pointer.playbook == "TestPlaybook"
        assert call_args.instruction_pointer.line_number == "02"

        # Test YLD at the last line of a playbook
        step_collection = PlaybookStepCollection()
        step_collection.add_step(
            PlaybookStep(
                "01", "QUE", "Say(message='Hello')", "01:QUE: Say(message='Hello')"
            )
        )
        step_collection.add_step(
            PlaybookStep("02", "YLD", "ForUserInput", "02:YLD: ForUserInput")
        )

        current_playbook.get_step.side_effect = lambda ln: step_collection.get_step(ln)
        current_playbook.get_next_step.side_effect = (
            lambda ln: step_collection.get_next_step(ln)
        )

        interpreter.call_stack.reset_mock()
        interpreter_execution._update_call_stack("TestPlaybook:02:YLD", [])

        # Verify the call stack was popped but no new frame was pushed
        assert interpreter.call_stack.pop.call_count == 1
        assert interpreter.call_stack.push.call_count == 0

        # Test YLD followed by RET
        step_collection = PlaybookStepCollection()
        step_collection.add_step(
            PlaybookStep(
                "01", "QUE", "Say(message='Hello')", "01:QUE: Say(message='Hello')"
            )
        )
        step_collection.add_step(
            PlaybookStep("02", "YLD", "ForUserInput", "02:YLD: ForUserInput")
        )
        step_collection.add_step(
            PlaybookStep("03", "RET", "return result", "03:RET: return result")
        )

        current_playbook.get_step.side_effect = lambda ln: step_collection.get_step(ln)
        current_playbook.get_next_step.side_effect = (
            lambda ln: step_collection.get_next_step(ln)
        )

        interpreter.call_stack.reset_mock()
        interpreter_execution._update_call_stack("TestPlaybook:02:YLD", [])

        # Verify a new frame was pushed with the next line number (RET)
        assert interpreter.call_stack.pop.call_count == 1
        assert interpreter.call_stack.push.call_count == 1
        call_args = interpreter.call_stack.push.call_args[0][0]
        assert call_args.instruction_pointer.playbook == "TestPlaybook"
        assert call_args.instruction_pointer.line_number == "03"

    def test_update_call_stack_with_nested_yld(self):
        """Test updating call stack with a YLD instruction in nested lines."""
        interpreter = MagicMock()
        interpreter.call_stack.peek.return_value = None

        # Create a step collection with nested test steps
        step_collection = PlaybookStepCollection()
        step_collection.add_step(
            PlaybookStep("01", "LOP", "For each item", "01:LOP: For each item")
        )
        step_collection.add_step(
            PlaybookStep(
                "01.01",
                "QUE",
                "Say(message='Processing')",
                "01.01:QUE: Say(message='Processing')",
            )
        )
        step_collection.add_step(
            PlaybookStep("01.02", "YLD", "ForUserInput", "01.02:YLD: ForUserInput")
        )
        step_collection.add_step(
            PlaybookStep(
                "01.03", "QUE", "Say(message='Done')", "01.03:QUE: Say(message='Done')"
            )
        )
        step_collection.add_step(
            PlaybookStep("02", "RET", "return result", "02:RET: return result")
        )

        # Mock the current playbook with step collection
        current_playbook = MagicMock()
        current_playbook.get_step.side_effect = lambda ln: step_collection.get_step(ln)
        current_playbook.get_next_step.side_effect = (
            lambda ln: step_collection.get_next_step(ln)
        )

        interpreter_execution = InterpreterExecution(
            interpreter=interpreter,
            playbooks={},
            current_playbook=current_playbook,
            instruction="Test instruction",
        )

        # Test nested YLD instruction advances to the next sub-line
        interpreter_execution._update_call_stack("TestPlaybook:01.02:YLD", [])

        # Verify the call stack was updated correctly
        assert interpreter.call_stack.pop.call_count == 1

        # Verify a new frame was pushed with the next line number
        assert interpreter.call_stack.push.call_count == 1
        call_args = interpreter.call_stack.push.call_args[0][0]
        assert call_args.instruction_pointer.playbook == "TestPlaybook"
        assert call_args.instruction_pointer.line_number == "01.03"

        # Test YLD at the last nested line
        step_collection = PlaybookStepCollection()
        step_collection.add_step(
            PlaybookStep("01", "LOP", "For each item", "01:LOP: For each item")
        )
        step_collection.add_step(
            PlaybookStep(
                "01.01",
                "QUE",
                "Say(message='Processing')",
                "01.01:QUE: Say(message='Processing')",
            )
        )
        step_collection.add_step(
            PlaybookStep("01.02", "YLD", "ForUserInput", "01.02:YLD: ForUserInput")
        )

        current_playbook.get_step.side_effect = lambda ln: step_collection.get_step(ln)
        current_playbook.get_next_step.side_effect = (
            lambda ln: step_collection.get_next_step(ln)
        )

        interpreter.call_stack.reset_mock()
        interpreter_execution._update_call_stack("TestPlaybook:01.02:YLD", [])

        # With the new DAG-based navigation, the last step in a loop loops back to the first step
        # Verify the call stack was popped and a new frame was pushed with the first line in the loop
        assert interpreter.call_stack.pop.call_count == 1
        assert interpreter.call_stack.push.call_count == 1
        call_args = interpreter.call_stack.push.call_args[0][0]
        assert call_args.instruction_pointer.playbook == "TestPlaybook"
        assert call_args.instruction_pointer.line_number in ["01", "01.01"]

    def test_returning_from_playbook_call(self):
        """Test that returning from a playbook call properly manages the call stack.

        This is a regression test for the issue where returning from a playbook call
        would result in duplicate frames in the call stack.
        """
        # Set up the interpreter with a mock call stack
        interpreter = MagicMock()
        # Mock handle_empty_call_stack to return (False, None)
        interpreter.handle_empty_call_stack.return_value = (False, None)

        # Create a step collection for the main playbook
        main_step_collection = PlaybookStepCollection()
        main_step_collection.add_step(
            PlaybookStep(
                "05.01.03",
                "QUE",
                "Call GatherRelevantInformation",
                "05.01.03:QUE: Call GatherRelevantInformation",
            )
        )
        main_step_collection.add_step(
            PlaybookStep(
                "05.01.04",
                "QUE",
                "Next step after call",
                "05.01.04:QUE: Next step after call",
            )
        )

        # Create a step collection for the called playbook
        gather_step_collection = PlaybookStepCollection()
        gather_step_collection.add_step(
            PlaybookStep(
                "01.05",
                "RET",
                "Return from GatherRelevantInformation",
                "01.05:RET: Return from GatherRelevantInformation",
            )
        )

        # Mock the playbooks
        main_playbook = MagicMock()
        main_playbook.klass = "Main"
        main_playbook.get_step.side_effect = lambda ln: main_step_collection.get_step(
            ln
        )
        main_playbook.get_next_step.side_effect = (
            lambda ln: main_step_collection.get_next_step(ln)
        )

        gather_playbook = MagicMock()
        gather_playbook.klass = "GatherRelevantInformation"
        gather_playbook.get_step.side_effect = (
            lambda ln: gather_step_collection.get_step(ln)
        )
        gather_playbook.get_next_step.side_effect = (
            lambda ln: gather_step_collection.get_next_step(ln)
        )

        playbooks = {
            "Main": main_playbook,
            "GatherRelevantInformation": gather_playbook,
        }

        # Create the interpreter execution with the GatherRelevantInformation playbook
        interpreter_execution = InterpreterExecution(
            interpreter=interpreter,
            playbooks=playbooks,
            current_playbook=gather_playbook,
            instruction="Test instruction",
        )

        # Mock the call stack to simulate returning from GatherRelevantInformation to Main
        # The call stack should have Main:05.01.03 at the bottom and GatherRelevantInformation:01.05 at the top
        def mock_get_current_playbook_name():
            # After popping GatherRelevantInformation:01.05, we should be at Main:05.01.03
            return "Main"

        interpreter.get_current_playbook_name.side_effect = (
            mock_get_current_playbook_name
        )

        # Execute the RET instruction from GatherRelevantInformation
        result = interpreter_execution._update_call_stack(
            "GatherRelevantInformation:01.05:RET", []
        )

        # Verify the call stack was popped
        assert interpreter.call_stack.pop.call_count == 1

        # Verify no new frame was pushed (we should just return to the calling frame)
        assert interpreter.call_stack.push.call_count == 0

        # Verify the result indicates we should continue execution
        assert result is False

        # Now test the execute method's handling of returning from a playbook call
        # Create a new interpreter execution for this test
        interpreter = MagicMock()
        # Mock handle_empty_call_stack to return (False, None)
        interpreter.handle_empty_call_stack.return_value = (False, None)

        # Mock get_current_playbook_name to return the same as current_playbook.klass
        # to avoid triggering the "Switching to playbook" exit condition
        interpreter.get_current_playbook_name.return_value = "GatherRelevantInformation"

        # Create a mock call stack with a frame
        mock_frame = MagicMock()
        mock_frame.instruction_pointer.playbook = "GatherRelevantInformation"
        mock_frame.instruction_pointer.line_number = "01.05"
        interpreter.call_stack.peek.return_value = mock_frame

        interpreter_execution = InterpreterExecution(
            interpreter=interpreter,
            playbooks=playbooks,
            current_playbook=gather_playbook,
            instruction="Test instruction",
        )

        # Mock the execution_loop to ensure it terminates after one iteration
        with patch.object(
            interpreter_execution, "execution_loop"
        ) as mock_execution_loop:
            # Create a context manager that will only allow one iteration
            @contextlib.contextmanager
            def mock_loop():
                counter = [0]

                def check_continue():
                    if counter[0] < 1:
                        counter[0] += 1
                        return True
                    return False

                try:
                    yield check_continue
                finally:
                    pass

            mock_execution_loop.return_value = mock_loop()

            # Mock the necessary methods for the execute method
            interpreter_execution._prepare_instruction = MagicMock(
                return_value="Test instruction"
            )
            interpreter_execution._get_llm_response = MagicMock(
                return_value=[AgentResponseChunk(raw="Test response")]
            )
            interpreter_execution.parse_response = MagicMock(
                return_value=(
                    [],  # tool_calls
                    "GatherRelevantInformation:01.05:RET",  # last_executed_step
                    {},  # updated_variables
                )
            )
            interpreter_execution._annotate_tool_calls = MagicMock(return_value=[])
            interpreter_execution._process_tool_calls = MagicMock()

            # Instead of mocking _update_call_stack completely, we'll use a side_effect
            # that simulates the call stack reduction but doesn't change the current playbook
            def mock_update_call_stack(last_executed_step, playbook_calls):
                # Store the call stack state before and after
                interpreter_execution.call_stack_before = [
                    "Main:05.01.03",
                    "GatherRelevantInformation:01.05",
                ]
                interpreter_execution.call_stack_after = ["Main:05.01.03"]
                # Set the should_exit flag directly to ensure the loop terminates
                interpreter_execution.should_exit = True
                interpreter_execution.exit_reason = "Returning from playbook call"
                return False

            interpreter_execution._update_call_stack = MagicMock(
                side_effect=mock_update_call_stack
            )
            interpreter_execution._check_exit_conditions = MagicMock(return_value=False)

            # Execute the interpreter
            list(interpreter_execution.execute())

            # Verify that should_exit was set to True when returning from the playbook call
            assert interpreter_execution.should_exit is True
            assert interpreter_execution.exit_reason == "Returning from playbook call"
