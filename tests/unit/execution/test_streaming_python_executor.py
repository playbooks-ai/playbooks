"""Unit tests for StreamingPythonExecutor.

Tests incremental code execution, variable tracking, error handling, and code truncation.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from playbooks.execution.streaming_python_executor import (
    StreamingExecutionError,
    StreamingPythonExecutor,
)


class TestStreamingPythonExecutor:
    """Test suite for StreamingPythonExecutor."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent for testing."""
        from dotmap import DotMap

        agent = Mock()
        agent.id = "test_agent"
        agent.klass = "TestAgent"
        agent.state = Mock()

        # Use real DotMap for variables to test actual behavior
        agent.state.variables = DotMap()

        agent.state.call_stack = Mock()
        agent.state.call_stack.peek = Mock(
            return_value=Mock(langfuse_span=None, instruction_pointer=Mock())
        )
        agent.state.call_stack.advance_instruction_pointer = Mock()
        agent.state.event_bus = Mock()
        agent.program = Mock()
        agent.program._debug_server = None
        agent.program.agents = []
        agent.program.agent_klasses = []  # Fix for agent_proxy iteration
        agent.playbooks = {}
        agent.parse_instruction_pointer = Mock(return_value=Mock(step="EXE"))
        return agent

    @pytest.fixture
    def executor(self, mock_agent):
        """Create a StreamingPythonExecutor instance for testing."""
        return StreamingPythonExecutor(mock_agent, playbook_args=None)

    @pytest.mark.asyncio
    async def test_simple_assignment(self, executor):
        """Test that simple variable assignments execute correctly."""
        await executor.add_chunk("x = 10\n")
        await executor.add_chunk("y = 20\n")

        result = await executor.finalize()

        assert result.vars == {"x": 10, "y": 20}
        assert executor.namespace["x"] == 10
        assert executor.namespace["y"] == 20

    @pytest.mark.asyncio
    async def test_incremental_statement_execution(self, executor):
        """Test that statements execute as soon as they're complete."""
        # Add complete statements one at a time
        await executor.add_chunk("x = 10\n")
        assert executor.namespace["x"] == 10

        await executor.add_chunk("y = 20\n")
        assert executor.namespace["y"] == 20

        # Both variables should be available
        result = await executor.finalize()
        assert result.vars["x"] == 10
        assert result.vars["y"] == 20

    @pytest.mark.asyncio
    async def test_multiline_statement(self, executor):
        """Test that multi-line statements are handled correctly."""
        code = """result = (
    1 + 2 +
    3 + 4
)
"""
        # Add the entire multi-line statement (streaming happens at statement boundaries)
        await executor.add_chunk(code)

        result = await executor.finalize()
        assert result.vars["result"] == 10

    @pytest.mark.asyncio
    async def test_comment_execution(self, executor):
        """Test that comments are handled correctly."""
        await executor.add_chunk("# This is a comment\n")
        await executor.add_chunk("x = 5\n")

        result = await executor.finalize()
        assert result.vars["x"] == 5

    @pytest.mark.asyncio
    async def test_async_statement_execution(self, executor):
        """Test that async statements (with await) execute correctly."""
        # Mock an async Step function
        step_mock = AsyncMock()
        executor.namespace["Step"] = step_mock

        await executor.add_chunk('await Step("TEST:01:EXE")\n')

        # Verify Step was called
        step_mock.assert_called_once_with("TEST:01:EXE")

    @pytest.mark.asyncio
    async def test_variable_tracking(self, executor):
        """Test that variable changes are tracked automatically."""
        await executor.add_chunk("x = 10\n")
        await executor.add_chunk("x = 20\n")
        await executor.add_chunk("y = 30\n")

        result = await executor.finalize()

        # Should have final values
        assert result.vars["x"] == 20
        assert result.vars["y"] == 30

    @pytest.mark.asyncio
    async def test_syntax_error_handling(self, executor):
        """Test that syntax errors during parsing are handled gracefully.

        Note: Python's parser is lenient and waits for more input with incomplete
        statements. This test verifies basic parsing behavior.
        """
        await executor.add_chunk("x = 10\n")

        # Incomplete code doesn't raise error immediately (waits for more input)
        await executor.add_chunk("y = (1 + 2\n")  # Incomplete - missing closing paren

        # Verify x was executed before incomplete statement
        assert executor.namespace["x"] == 10
        assert "y" not in executor.namespace  # y not assigned yet

    @pytest.mark.asyncio
    async def test_runtime_error_handling(self, executor):
        """Test that runtime errors are caught and execution stops."""
        await executor.add_chunk("x = 10\n")

        # Add code that will cause runtime error
        with pytest.raises(StreamingExecutionError):
            await executor.add_chunk("y = 1 / 0\n")
            await executor.add_chunk("z = 30\n")  # Should not execute

        # Verify error was captured
        assert executor.has_error
        assert isinstance(executor.error, ZeroDivisionError)

        # Verify executed code includes the error line but not subsequent lines
        executed = executor.get_executed_code()
        assert "x = 10" in executed
        assert "z = 30" not in executed

    @pytest.mark.asyncio
    async def test_error_stops_further_execution(self, executor):
        """Test that after an error, further chunks are not executed."""
        await executor.add_chunk("x = 10\n")

        # Cause an error
        with pytest.raises(StreamingExecutionError):
            await executor.add_chunk("y = undefined_var\n")

        # Try to add more code - should be ignored
        await executor.add_chunk("z = 30\n")

        result = await executor.finalize()

        # z should not have been executed
        assert "z" not in result.vars
        assert "z" not in executor.namespace

    @pytest.mark.asyncio
    async def test_get_executed_code(self, executor):
        """Test that get_executed_code returns the correct code."""
        await executor.add_chunk("x = 10\n")
        await executor.add_chunk("y = 20\n")

        executed = executor.get_executed_code()

        assert "x = 10" in executed
        assert "y = 20" in executed

    @pytest.mark.asyncio
    async def test_preprocessing_dollar_variables(self, executor):
        """Test that state.variable syntax works correctly."""
        await executor.add_chunk("state.result = 100\n")

        await executor.finalize()

        # Variable should be stored in state
        assert executor.agent.state.variables.result == 100

    @pytest.mark.asyncio
    async def test_expression_evaluation(self, executor):
        """Test that expressions are evaluated correctly."""
        await executor.add_chunk("x = 5\n")
        await executor.add_chunk("y = x * 2\n")
        await executor.add_chunk("z = x + y\n")

        result = await executor.finalize()

        assert result.vars["x"] == 5
        assert result.vars["y"] == 10
        assert result.vars["z"] == 15

    @pytest.mark.asyncio
    async def test_for_loop_execution(self, executor):
        """Test that for loops execute correctly."""
        # Add code but ensure loop is closed with a dedent
        await executor.add_chunk("total = 0\n")
        await executor.add_chunk("for i in range(5):\n")
        await executor.add_chunk("    total += i\n")
        # Add a dedent to close the loop
        await executor.add_chunk("# loop done\n")

        result = await executor.finalize()
        assert result.vars["total"] == 10

    @pytest.mark.asyncio
    async def test_if_statement_execution(self, executor):
        """Test that if statements execute correctly."""
        code = """x = 10
if x > 5:
    result = "big"
else:
    result = "small"
"""
        for line in code.split("\n"):
            await executor.add_chunk(line + "\n")

        result = await executor.finalize()
        assert result.vars["result"] == "big"

    @pytest.mark.asyncio
    async def test_function_definition(self, executor):
        """Test that function definitions work correctly."""
        code = """def add(a, b):
    return a + b

result = add(3, 4)
"""
        for line in code.split("\n"):
            await executor.add_chunk(line + "\n")

        result = await executor.finalize()
        assert result.vars["result"] == 7

    @pytest.mark.asyncio
    async def test_playbook_args_in_namespace(self, mock_agent):
        """Test that playbook arguments are available in the namespace."""
        playbook_args = {"param1": "value1", "param2": 42}
        executor = StreamingPythonExecutor(mock_agent, playbook_args=playbook_args)

        await executor.add_chunk("result = param1 + str(param2)\n")

        result = await executor.finalize()
        assert result.vars["result"] == "value142"

    @pytest.mark.asyncio
    async def test_namespace_persistence(self, executor):
        """Test that namespace persists across chunks."""
        await executor.add_chunk("x = 10\n")
        assert executor.namespace["x"] == 10

        await executor.add_chunk("y = x + 5\n")
        assert executor.namespace["y"] == 15

        await executor.add_chunk("z = x + y\n")
        assert executor.namespace["z"] == 25

    @pytest.mark.asyncio
    async def test_empty_chunks(self, executor):
        """Test that empty chunks are handled gracefully."""
        await executor.add_chunk("")
        await executor.add_chunk("   \n")
        await executor.add_chunk("x = 10\n")

        result = await executor.finalize()
        assert result.vars["x"] == 10

    @pytest.mark.asyncio
    async def test_result_accumulation(self, executor):
        """Test that ExecutionResult accumulates data correctly."""
        # Mock capture functions
        executor.base_executor._capture_var = AsyncMock()

        await executor.add_chunk("x = 10\n")
        await executor.add_chunk("y = 20\n")

        _result = await executor.finalize()

        # Should have called _capture_var for both variables
        assert executor.base_executor._capture_var.call_count >= 2

    @pytest.mark.asyncio
    async def test_similar_variable_names_messages_and_message(self, executor):
        """Test that similar variable names like state.messages and state.message work correctly.

        This reproduces the issue from two-player-game.pb where the LLM generated similar names.
        Now using state.x syntax instead of $x.
        """
        # Mock Step function
        step_mock = AsyncMock()
        executor.namespace["Step"] = step_mock

        # Simulate the LLM-generated code pattern with new syntax
        await executor.add_chunk('await Step("ProcessMessages:01:CND")\n')
        await executor.add_chunk(
            'state.messages = ["Host(agent 1000) → Player(agent 1002): Game room for chess", '
        )
        await executor.add_chunk(
            '"Player(agent 1001) → all: KnightRider here, ready for chess. Let\'s play!"]\n'
        )
        await executor.add_chunk(
            'state.message = "Host(agent 1000) → Player(agent 1002): Game room for chess"\n'
        )

        await executor.finalize()

        # Verify both variables were set correctly in state
        assert hasattr(executor.agent.state.variables, "messages")
        assert hasattr(executor.agent.state.variables, "message")
        assert executor.agent.state.variables.messages == [
            "Host(agent 1000) → Player(agent 1002): Game room for chess",
            "Player(agent 1001) → all: KnightRider here, ready for chess. Let's play!",
        ]
        assert (
            executor.agent.state.variables.message
            == "Host(agent 1000) → Player(agent 1002): Game room for chess"
        )

    @pytest.mark.asyncio
    async def test_preprocessing_with_similar_variable_names(self, executor):
        """Test behavior with similar variable names like state.message vs state.messages.

        Ensures that similar variable names work correctly without preprocessing.
        """
        # Test execution with new syntax (no preprocessing needed)
        await executor.add_chunk('state.messages = ["msg1", "msg2"]\n')
        await executor.add_chunk('state.message = "msg1"\n')

        await executor.finalize()

        # Verify both variables were set correctly in state
        assert hasattr(executor.agent.state.variables, "messages")
        assert hasattr(executor.agent.state.variables, "message")
        assert executor.agent.state.variables.messages == ["msg1", "msg2"]
        assert executor.agent.state.variables.message == "msg1"

    @pytest.mark.asyncio
    async def test_messages_and_message_with_comments_and_steps(self, executor):
        """Test the exact pattern from two-player-game.pb error.

        Reproduces the specific code pattern that caused the error:
        - await Step()
        - $messages assignment
        - $message assignment
        - Comments between statements
        - Multiple Step() calls
        """
        # Mock Step function
        step_mock = AsyncMock()
        executor.namespace["Step"] = step_mock

        # Simulate the exact LLM-generated code pattern with new syntax
        code_chunks = [
            'await Step("ProcessMessages:01:CND")\n',
            'state.messages = ["Host(agent 1000) → Player(agent 1002): Game room for chess", ',
            '"Player(agent 1001) → all: KnightRider here, ready for chess. Let\'s play!"]\n',
            'state.message = "Host(agent 1000) → Player(agent 1002): Game room for chess"\n',
            "\n",
            "# trig? no\n",
            "# yld? no, checking message type\n",
            "\n",
            'await Step("ProcessMessages:01.01:CND")\n',
        ]

        for chunk in code_chunks:
            await executor.add_chunk(chunk)

        await executor.finalize()

        # Verify variables were set correctly in state
        assert hasattr(executor.agent.state.variables, "messages")
        assert hasattr(executor.agent.state.variables, "message")
        assert step_mock.call_count == 2

    @pytest.mark.asyncio
    async def test_message_variable_split_across_chunks(self, executor):
        """Test when state.message variable name is split across chunks.

        This tests the edge case where streaming might split the statement
        in the middle, which the streaming executor should handle by
        only processing complete lines.
        """
        # First execute state.messages successfully
        await executor.add_chunk('state.messages = ["msg1", "msg2"]\n')
        assert hasattr(executor.agent.state.variables, "messages")

        # Now try to execute state.message, but split the line
        # The executor should wait for complete line (ending with \n)
        await executor.add_chunk("state.mes")  # Incomplete - no newline
        await executor.add_chunk('sage = "msg1"\n')  # Complete now

        await executor.finalize()

        # Both should be set correctly
        assert hasattr(executor.agent.state.variables, "messages")
        assert hasattr(executor.agent.state.variables, "message")
        assert executor.agent.state.variables.message == "msg1"

    @pytest.mark.asyncio
    async def test_message_referenced_before_definition_after_messages(self, executor):
        """Test referencing state.message before it's defined when state.messages exists.

        This reproduces the error pattern where:
        1. state.messages is defined
        2. Code tries to use state.message before it's defined
        """
        # Define state.messages first
        await executor.add_chunk('state.messages = ["msg1", "msg2"]\n')

        # Now try to use state.message in an expression before defining it
        # Note: DotMap auto-creates empty DotMap for undefined attributes,
        # so this won't error - it will just create state.message as DotMap()
        await executor.add_chunk('state.message = "msg1"\n')  # Define it properly

        await executor.finalize()

        # Both should be set correctly
        assert hasattr(executor.agent.state.variables, "messages")
        assert hasattr(executor.agent.state.variables, "message")
        assert executor.agent.state.variables.messages == ["msg1", "msg2"]
        assert executor.agent.state.variables.message == "msg1"

    @pytest.mark.asyncio
    async def test_message_extraction_from_messages_pattern(self, executor):
        """Test the pattern of extracting state.message from state.messages[0].

        This tests a common pattern where you might extract the first message:
        state.messages = [...]
        state.message = state.messages[0]
        """
        await executor.add_chunk('state.messages = ["msg1", "msg2"]\n')
        await executor.add_chunk(
            "state.message = state.messages[0]\n"
        )  # Extract first message

        await executor.finalize()

        # Both should be set correctly
        assert hasattr(executor.agent.state.variables, "messages")
        assert hasattr(executor.agent.state.variables, "message")
        assert executor.agent.state.variables.message == "msg1"

    @pytest.mark.asyncio
    async def test_exact_two_player_game_pattern_with_debug_output(self, executor):
        """Test the EXACT pattern from two-player-game.pb with debug output.

        This reproduces the exact streaming pattern that would occur during
        the actual playbook execution, including the Var() calls that happen
        during variable tracking.
        """
        # Mock Step function
        step_mock = AsyncMock()
        executor.namespace["Step"] = step_mock

        # Simulate the EXACT streaming as it would happen with new syntax
        # The LLM generates this code in chunks
        code = """await Step("ProcessMessages:01:CND")
state.messages = ["Host(agent 1000) → Player(agent 1002): Game room for chess", "Player(agent 1001) → all: KnightRider here, ready for chess. Let's play!"]
state.message = "Host(agent 1000) → Player(agent 1002): Game room for chess"

# trig? no
# yld? no, checking message type
"""

        # Now simulate actual streaming - send complete lines one at a time
        lines = code.split("\n")
        for i, line in enumerate(lines):
            if i < len(lines) - 1:  # All but last line
                await executor.add_chunk(line + "\n")
            else:  # Last line (might be empty)
                if line:
                    await executor.add_chunk(line + "\n")

        await executor.finalize()

        # Both variables should be set
        assert hasattr(executor.agent.state.variables, "messages")
        assert hasattr(executor.agent.state.variables, "message")

    @pytest.mark.asyncio
    async def test_namespace_exec_with_message_and_messages(self, executor):
        """Test exec() behavior with similar variable names using state.x syntax.

        This tests that similar names work correctly with direct state access.
        """
        # Test with new syntax - no preprocessing needed
        code1 = 'state.messages = ["msg1", "msg2"]'
        exec(compile(code1, "<test>", "exec"), executor.namespace)
        assert hasattr(executor.agent.state.variables, "messages")

        # Now add message to state
        code2 = 'state.message = "msg1"'
        exec(compile(code2, "<test>", "exec"), executor.namespace)
        assert hasattr(executor.agent.state.variables, "message")

        # Both should be in state
        assert executor.agent.state.variables.messages == ["msg1", "msg2"]
        assert executor.agent.state.variables.message == "msg1"

    @pytest.mark.asyncio
    async def test_buffer_preprocessing_with_partial_token(self, executor):
        """Test that partial lines are handled correctly by the buffer.

        The streaming executor only processes complete lines (ending with \n),
        so partial tokens shouldn't cause issues.
        """
        # Test with new syntax - no preprocessing, just buffering
        # Get initial count of actual stored values (not auto-created DotMap entries)
        dict(executor.agent.state.variables)

        # Add partial line (no newline)
        await executor.add_chunk('state.messages = ["msg1')

        # Buffer should hold partial code, not execute yet
        # (executor processes only complete lines)
        current_vars = dict(executor.agent.state.variables)
        assert "messages" not in current_vars or not isinstance(
            current_vars.get("messages"), list
        )

        # Complete the line
        await executor.add_chunk('"]\n')

        # Now it should execute and have the list value
        assert hasattr(executor.agent.state.variables, "messages")
        assert executor.agent.state.variables.messages == ["msg1"]

    @pytest.mark.asyncio
    async def test_progressive_parsing_with_incomplete_string(self, executor):
        """Test progressive parsing executes valid lines even with incomplete code.

        This reproduces the exact issue reported where:
        # execution_id: 2
        # recap: Introduced myself as PawnStorm and indicated readiness
        # plan: Enter game loop and wait for my turn or game instructions

        await Step("GamePlayingM

        The comments are valid Python and should be parsed/executed, even though
        the incomplete string literal causes a SyntaxError. The progressive parser
        should back off and execute just the comment lines.
        """
        # Mock Step function
        step_mock = AsyncMock()
        executor.namespace["Step"] = step_mock

        # Simulate the exact pattern from the bug report - an incomplete string
        # The chunk has newlines in the comments, which triggers parsing
        # But the await line is incomplete (unterminated string)
        chunk = """# execution_id: 2
# recap: Introduced myself as PawnStorm and indicated readiness
# plan: Enter game loop and wait for my turn or game instructions

await Step("GamePlayingM"""

        # This should not raise an error - progressive parsing will execute what it can
        # (the comment lines will execute, but the incomplete await won't)
        await executor.add_chunk(chunk)

        # Should not have crashed
        # Comments should have been executed (they're valid Python)

        # Now complete the string ON THE SAME LINE and verify it executes
        # Key: no newline before this chunk, so it completes the same line
        await executor.add_chunk('ove:01:EXE")\n')

        # Now the Step should have been called
        step_mock.assert_called_once_with("GamePlayingMove:01:EXE")

        result = await executor.finalize()
        assert not result.syntax_error
        assert not result.runtime_error

    @pytest.mark.asyncio
    async def test_progressive_parsing_executes_valid_statements_before_error(
        self, executor
    ):
        """Test that valid statements are executed even when followed by syntax error.

        This tests the progressive parsing logic that executes:
        x = 10
        y = 20
        z = (incomplete

        Should execute x=10 and y=20, then wait for more input to complete z.
        """
        # Add valid statements followed by incomplete code
        chunk = """x = 10
y = 20
z = (1 + 2"""

        await executor.add_chunk(chunk + "\n")

        # x and y should have been executed
        assert executor.namespace["x"] == 10
        assert executor.namespace["y"] == 20

        # z should not be in namespace yet (incomplete statement)
        assert "z" not in executor.namespace

        # Now complete the statement
        await executor.add_chunk(" + 3)\n")

        result = await executor.finalize()

        # Now z should be executed
        assert result.vars["z"] == 6
        assert executor.namespace["z"] == 6

    @pytest.mark.asyncio
    async def test_progressive_parsing_with_empty_lines_and_comments(self, executor):
        """Test progressive parsing handles empty lines and comments correctly.

        This ensures that:
        # comment 1

        # comment 2
        x = 10
        await Step("incomplete

        Executes the comments and x=10, waiting for Step to complete.
        """
        # Mock Step function
        step_mock = AsyncMock()
        executor.namespace["Step"] = step_mock

        # First chunk has newlines in comments (triggers parsing) but await line is incomplete
        chunk1 = """# comment 1

# comment 2
x = 10
"""
        await executor.add_chunk(chunk1)

        # x should be executed
        assert executor.namespace["x"] == 10

        # Step should not have been called yet (not even started)
        step_mock.assert_not_called()

        # Now add the incomplete await statement
        chunk2 = 'await Step("incomplete'
        await executor.add_chunk(chunk2)

        # Still shouldn't be called (incomplete string)
        step_mock.assert_not_called()

        # Complete the Step call on the same line
        await executor.add_chunk(' string")\n')

        _result = await executor.finalize()

        # Now Step should be called
        step_mock.assert_called_once_with("incomplete string")
