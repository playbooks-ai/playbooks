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
        agent = Mock()
        agent.id = "test_agent"
        agent.klass = "TestAgent"
        agent.state = Mock()

        # Create a dict-like mock for variables that supports 'in' operator
        variables_dict = {}
        agent.state.variables = Mock()
        agent.state.variables.to_dict = Mock(return_value=variables_dict)
        agent.state.variables.__setitem__ = Mock(
            side_effect=lambda name, value, **kwargs: variables_dict.__setitem__(
                name, value
            )
        )
        agent.state.variables.__contains__ = Mock(
            side_effect=lambda k: k in variables_dict
        )
        agent.state.variables.__getitem__ = Mock(
            side_effect=lambda k: variables_dict[k]
        )

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
        """Test that $variable syntax is preprocessed correctly."""
        await executor.add_chunk("$result = 100\n")

        result = await executor.finalize()

        # Variable should be stored without $ prefix
        assert result.vars["result"] == 100
        assert executor.namespace["result"] == 100

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
        """Test that similar variable names like $messages and $message work correctly.

        This reproduces the issue from two-player-game.pb where the LLM generated:
        $messages = [...]
        $message = "..."

        And got: NameError: name 'message' is not defined. Did you mean: 'messages'?
        """
        # Mock Step function
        step_mock = AsyncMock()
        executor.namespace["Step"] = step_mock

        # Simulate the LLM-generated code pattern
        await executor.add_chunk('await Step("ProcessMessages:01:CND")\n')
        await executor.add_chunk(
            '$messages = ["Host(agent 1000) → Player(agent 1002): Game room for chess", '
        )
        await executor.add_chunk(
            '"Player(agent 1001) → all: KnightRider here, ready for chess. Let\'s play!"]\n'
        )
        await executor.add_chunk(
            '$message = "Host(agent 1000) → Player(agent 1002): Game room for chess"\n'
        )

        result = await executor.finalize()

        # Verify both variables were set correctly
        assert "messages" in result.vars
        assert "message" in result.vars
        assert executor.namespace["messages"] == [
            "Host(agent 1000) → Player(agent 1002): Game room for chess",
            "Player(agent 1001) → all: KnightRider here, ready for chess. Let's play!",
        ]
        assert (
            executor.namespace["message"]
            == "Host(agent 1000) → Player(agent 1002): Game room for chess"
        )

    @pytest.mark.asyncio
    async def test_preprocessing_with_similar_variable_names(self, executor):
        """Test preprocessing behavior with $message vs $messages.

        Ensures that the preprocessing correctly distinguishes between
        similar variable names and doesn't incorrectly substitute one for another.
        """
        from playbooks.compilation.expression_engine import preprocess_program

        # Test preprocessing of similar variable names
        code = """$messages = ["msg1", "msg2"]
$message = "msg1"
print($message)
print($messages)"""

        preprocessed = preprocess_program(code)
        print(f"Original:\n{code}")
        print(f"\nPreprocessed:\n{preprocessed}")

        # Verify preprocessing converts both correctly
        assert "messages =" in preprocessed
        assert "message =" in preprocessed
        assert (
            "$messages" not in preprocessed or "$message" in preprocessed
        )  # Either both $ are gone or both present

        # Now test execution
        await executor.add_chunk('$messages = ["msg1", "msg2"]\n')
        await executor.add_chunk('$message = "msg1"\n')

        result = await executor.finalize()

        assert "messages" in result.vars
        assert "message" in result.vars

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

        # Simulate the exact LLM-generated code pattern from the error
        code_chunks = [
            'await Step("ProcessMessages:01:CND")\n',
            '$messages = ["Host(agent 1000) → Player(agent 1002): Game room for chess", ',
            '"Player(agent 1001) → all: KnightRider here, ready for chess. Let\'s play!"]\n',
            '$message = "Host(agent 1000) → Player(agent 1002): Game room for chess"\n',
            "\n",
            "# trig? no\n",
            "# yld? no, checking message type\n",
            "\n",
            'await Step("ProcessMessages:01.01:CND")\n',
        ]

        for chunk in code_chunks:
            await executor.add_chunk(chunk)

        result = await executor.finalize()

        # Verify variables were set correctly
        assert "messages" in result.vars
        assert "message" in result.vars
        assert step_mock.call_count == 2

    @pytest.mark.asyncio
    async def test_message_variable_split_across_chunks(self, executor):
        """Test when $message variable name is split across chunks.

        This tests the edge case where streaming might split $message
        in the middle, which the streaming executor should handle by
        only processing complete lines.
        """
        # First execute $messages successfully
        await executor.add_chunk('$messages = ["msg1", "msg2"]\n')
        assert "messages" in executor.namespace

        # Now try to execute $message, but split the variable name
        # The executor should wait for complete line (ending with \n)
        await executor.add_chunk("$mes")  # Incomplete - no newline
        await executor.add_chunk('sage = "msg1"\n')  # Complete now

        result = await executor.finalize()

        # Both should be set correctly
        assert "messages" in result.vars
        assert "message" in result.vars
        assert executor.namespace["message"] == "msg1"

    @pytest.mark.asyncio
    async def test_message_referenced_before_definition_after_messages(self, executor):
        """Test referencing $message before it's defined when $messages exists.

        This reproduces the exact error from two-player-game.pb:
        NameError: name 'message' is not defined. Did you mean: 'messages'?

        The issue occurs when:
        1. $messages is defined
        2. Code tries to use $message before it's defined
        """
        # Define $messages first
        await executor.add_chunk('$messages = ["msg1", "msg2"]\n')

        # Now try to use $message in an expression before defining it
        # This should fail with NameError since $message hasn't been defined yet
        from playbooks.execution.streaming_python_executor import (
            StreamingExecutionError,
        )

        with pytest.raises(StreamingExecutionError) as exc_info:
            await executor.add_chunk(
                'x = $message + " suffix"\n'
            )  # $message not yet defined

        # Verify it's the exact error we're looking for
        assert "NameError" in str(exc_info.value)
        assert "message" in str(exc_info.value).lower()

        # The error should also be captured in the result
        assert executor.result.runtime_error is not None
        assert "message" in str(executor.result.error_message).lower()

    @pytest.mark.asyncio
    async def test_message_extraction_from_messages_pattern(self, executor):
        """Test the pattern of extracting $message from $messages[0].

        This tests a common pattern where you might extract the first message:
        $messages = [...]
        $message = $messages[0]

        With preprocessing, this could potentially cause issues if there's
        a bug in how the substitution happens.
        """
        await executor.add_chunk('$messages = ["msg1", "msg2"]\n')
        await executor.add_chunk("$message = $messages[0]\n")  # Extract first message

        result = await executor.finalize()

        # Both should be set correctly
        assert "messages" in result.vars
        assert "message" in result.vars
        assert executor.namespace["message"] == "msg1"

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

        # Simulate the EXACT streaming as it would happen
        # The LLM generates this code in chunks
        code = """await Step("ProcessMessages:01:CND")
$messages = ["Host(agent 1000) → Player(agent 1002): Game room for chess", "Player(agent 1001) → all: KnightRider here, ready for chess. Let's play!"]
$message = "Host(agent 1000) → Player(agent 1002): Game room for chess"

# trig? no
# yld? no, checking message type
"""

        # Let's trace through what preprocessing does to this entire block
        from playbooks.compilation.expression_engine import preprocess_program

        preprocessed = preprocess_program(code)
        print(f"\n=== ORIGINAL CODE ===\n{code}")
        print(f"\n=== PREPROCESSED CODE ===\n{preprocessed}")

        # Now simulate actual streaming - send complete lines one at a time
        lines = code.split("\n")
        for i, line in enumerate(lines):
            if i < len(lines) - 1:  # All but last line
                await executor.add_chunk(line + "\n")
            else:  # Last line (might be empty)
                if line:
                    await executor.add_chunk(line + "\n")

        result = await executor.finalize()

        # Both variables should be set
        assert "messages" in result.vars or "messages" in executor.namespace
        assert "message" in result.vars or "message" in executor.namespace

    @pytest.mark.asyncio
    async def test_namespace_exec_with_message_and_messages(self, executor):
        """Test exec() behavior with similar variable names in namespace.

        This tests if there's an issue with how exec() handles variables
        when similar names exist in the namespace.
        """
        from playbooks.compilation.expression_engine import preprocess_program

        # First, add messages to namespace via exec
        code1 = '$messages = ["msg1", "msg2"]'
        preprocessed1 = preprocess_program(code1)
        print(f"\n=== Code 1: {code1}")
        print(f"=== Preprocessed 1: {preprocessed1}")

        # Execute it
        exec(compile(preprocessed1, "<test>", "exec"), executor.namespace)
        print(f"=== Namespace after statement 1: {list(executor.namespace.keys())}")
        assert "messages" in executor.namespace

        # Now add message to namespace
        code2 = '$message = "msg1"'
        preprocessed2 = preprocess_program(code2)
        print(f"\n=== Code 2: {code2}")
        print(f"=== Preprocessed 2: {preprocessed2}")

        # Execute it
        exec(compile(preprocessed2, "<test>", "exec"), executor.namespace)
        print(f"=== Namespace after statement 2: {list(executor.namespace.keys())}")
        assert "message" in executor.namespace

        # Both should be in namespace
        assert executor.namespace["messages"] == ["msg1", "msg2"]
        assert executor.namespace["message"] == "msg1"

    @pytest.mark.asyncio
    async def test_buffer_preprocessing_with_partial_token(self, executor):
        """Test what happens when preprocessing sees partial $message token.

        This tests if there's an issue where the buffer contains:
        $messages = [...]
        $mes

        And preprocessing might incorrectly handle it.
        """
        from playbooks.compilation.expression_engine import preprocess_program

        # Test 1: Complete code - should work
        complete_code = '$messages = ["msg1"]\n$message = "msg1"'
        preprocessed_complete = preprocess_program(complete_code)
        print(f"\n=== Complete code:\n{complete_code}")
        print(f"=== Preprocessed complete:\n{preprocessed_complete}")

        # Test 2: Partial code - what happens?
        partial_code = '$messages = ["msg1"]\n$mes'
        preprocessed_partial = preprocess_program(partial_code)
        print(f"\n=== Partial code:\n{partial_code}")
        print(f"=== Preprocessed partial:\n{preprocessed_partial}")

        # The partial should convert $mes to mes (even though it's incomplete)
        assert "messages" in preprocessed_complete
        assert "message" in preprocessed_complete
        assert "mes" in preprocessed_partial  # Should be converted even if incomplete

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
