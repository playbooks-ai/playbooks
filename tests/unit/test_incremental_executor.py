"""Tests for incremental Python code execution."""

import asyncio
import pytest

from playbooks.incremental_executor import IncrementalStatementParser


class TestIncrementalStatementParser:
    """Test the incremental statement parser."""

    def test_simple_comment(self):
        """Test parsing a simple comment."""
        parser = IncrementalStatementParser()

        # Add comment line by line
        statements = parser.add_chunk("# execution_id: 1\n")
        assert len(statements) == 1
        assert statements[0] == "# execution_id: 1"

    def test_simple_assignment(self):
        """Test parsing a simple assignment."""
        parser = IncrementalStatementParser()

        # Add partial assignment
        statements = parser.add_chunk("x = ")
        assert len(statements) == 0  # Incomplete

        # Complete the assignment
        statements = parser.add_chunk("10\n")
        assert len(statements) == 1
        assert statements[0].strip() == "x = 10"

    def test_multiline_string(self):
        """Test parsing multiline string (triple quotes)."""
        parser = IncrementalStatementParser()

        # Start multiline string
        statements = parser.add_chunk('msg = """\n')
        assert len(statements) == 0  # Incomplete

        # Add content
        statements = parser.add_chunk("Hello\n")
        assert len(statements) == 0  # Still incomplete

        # Add more content
        statements = parser.add_chunk("World\n")
        assert len(statements) == 0  # Still incomplete

        # Close multiline string
        statements = parser.add_chunk('"""\n')
        assert len(statements) == 1
        assert 'msg = """' in statements[0]
        assert "Hello" in statements[0]
        assert "World" in statements[0]

    def test_await_step(self):
        """Test parsing await Step() call."""
        parser = IncrementalStatementParser()

        # Add await call
        statements = parser.add_chunk('await Step("GameRoom:01:QUE")\n')
        assert len(statements) == 1
        assert statements[0].strip() == 'await Step("GameRoom:01:QUE")'

    def test_await_say(self):
        """Test parsing await Say() call."""
        parser = IncrementalStatementParser()

        # Add await Say with short message
        statements = parser.add_chunk('await Say("user", "Hello")\n')
        assert len(statements) == 1
        assert statements[0].strip() == 'await Say("user", "Hello")'

    def test_await_say_multiline(self):
        """Test parsing await Say() with multiline message."""
        parser = IncrementalStatementParser()

        # Start Say call
        statements = parser.add_chunk('await Say("user", """\n')
        assert len(statements) == 0  # Incomplete

        # Add message content
        statements = parser.add_chunk("Hello\n")
        assert len(statements) == 0  # Still incomplete

        # Close Say call
        statements = parser.add_chunk('""")\n')
        assert len(statements) == 1
        assert 'await Say("user", """' in statements[0]

    def test_for_loop(self):
        """Test parsing for loop."""
        parser = IncrementalStatementParser()

        # Add for statement
        statements = parser.add_chunk("for i in range(10):\n")
        assert len(statements) == 0  # Incomplete (expects body)

        # Add body - still incomplete (might have more statements in loop)
        statements = parser.add_chunk("    print(i)\n")
        assert len(statements) == 0  # Not complete yet!

        # Add dedent (blank line or lower indent) to signal end of loop
        statements = parser.add_chunk("\n")
        assert len(statements) == 1  # Now complete!
        assert "for i in range(10):" in statements[0]
        assert "print(i)" in statements[0]

    def test_dict_assignment(self):
        """Test parsing dictionary assignment."""
        parser = IncrementalStatementParser()

        # Start dict
        statements = parser.add_chunk("data = {\n")
        assert len(statements) == 0  # Incomplete

        # Add key-value
        statements = parser.add_chunk('    "name": "Alice",\n')
        assert len(statements) == 0  # Still incomplete

        # Add another key-value
        statements = parser.add_chunk('    "age": 30\n')
        assert len(statements) == 0  # Still incomplete

        # Close dict
        statements = parser.add_chunk("}\n")
        assert len(statements) == 1
        assert "data = {" in statements[0]
        assert '"name": "Alice"' in statements[0]

    def test_multiple_statements_in_one_chunk(self):
        """Test parsing multiple complete statements in one chunk."""
        parser = IncrementalStatementParser()

        chunk = """# execution_id: 1
await Step("Test:01")
x = 10
"""
        statements = parser.add_chunk(chunk)
        # Should return all complete statements
        assert len(statements) == 3
        assert statements[0].strip() == "# execution_id: 1"
        assert statements[1].strip() == 'await Step("Test:01")'
        assert statements[2].strip() == "x = 10"

    def test_incremental_complex_example(self):
        """Test parsing the complex example from requirements."""
        parser = IncrementalStatementParser()

        # Simulate streaming
        chunks = [
            "# execution_id: 4\n",
            "# recap: test\n",
            "# plan: test plan\n",
            "\n",
            'await Step("BAXY2:08:EXE")\n',
            "$result = $temp4 * $temp2\n",
            "\n",
            'await Step("BAXY2:09:RET")\n',
            "await Return($result)\n",
        ]

        all_statements = []
        for chunk in chunks:
            statements = parser.add_chunk(chunk)
            all_statements.extend(statements)

        # Should have parsed all statements
        assert len(all_statements) >= 6
        assert any("execution_id: 4" in s for s in all_statements)
        assert any('Step("BAXY2:08:EXE")' in s for s in all_statements)
        assert any("$result = $temp4 * $temp2" in s for s in all_statements)

    def test_nested_loops_with_indentation(self):
        """Test parsing nested loops with proper indentation tracking."""
        parser = IncrementalStatementParser()

        # Build the nested loop incrementally
        chunks = [
            "for i in range(3):\n",
            "  for j in range(2):\n",
            "    if i < j:\n",
            '      print("less")\n',
            '      print("hello")\n',
            "    else:\n",
            '      print("more")\n',
            '  print("j done")\n',
            # Dedent signals outer loop is complete
            'print("i done")\n',
        ]

        all_statements = []
        for chunk in chunks[:-1]:
            statements = parser.add_chunk(chunk)
            all_statements.extend(statements)
            # Nothing should be emitted until we see the dedent
            assert len(all_statements) == 0, f"Unexpected statement after {repr(chunk)}"

        # Last chunk has dedent - should emit the complete outer loop
        statements = parser.add_chunk(chunks[-1])
        assert len(statements) == 2  # The outer loop + the final print
        assert "for i in range(3):" in statements[0]
        assert "for j in range(2):" in statements[0]
        assert 'print("j done")' in statements[0]
        assert 'print("i done")' in statements[1]

    def test_syntax_error_detection(self):
        """Test that parser can detect syntax errors."""
        parser = IncrementalStatementParser()

        # Add invalid syntax
        statements = parser.add_chunk("if True\n")  # Missing colon
        # Parser should return empty (waiting for more) or detect error
        # We'll handle this in the actual implementation

    def test_buffer_state(self):
        """Test that parser maintains buffer state correctly."""
        parser = IncrementalStatementParser()

        # Add incomplete statement
        statements = parser.add_chunk("x = ")
        assert len(statements) == 0
        assert parser.buffer == "x = "  # Should keep in buffer

        # Complete it
        statements = parser.add_chunk("10\n")
        assert len(statements) == 1
        assert parser.buffer == ""  # Should clear buffer after parsing


class TestIncrementalExecutor:
    """Test the incremental executor."""

    @pytest.mark.asyncio
    async def test_execute_simple_comment(self):
        """Test executing a simple comment."""
        # TODO: Implement after creating IncrementalExecutor
        pass

    @pytest.mark.asyncio
    async def test_execute_assignment(self):
        """Test executing a simple assignment."""
        # TODO: Implement after creating IncrementalExecutor
        pass

    @pytest.mark.asyncio
    async def test_execute_await_step(self):
        """Test executing await Step()."""
        # TODO: Implement after creating IncrementalExecutor
        pass

    @pytest.mark.asyncio
    async def test_execute_with_error(self):
        """Test that errors are properly tracked."""
        # TODO: Implement after creating IncrementalExecutor
        pass

    @pytest.mark.asyncio
    async def test_variable_persistence(self):
        """Test that variables persist across statements."""
        # TODO: Implement after creating IncrementalExecutor
        pass
