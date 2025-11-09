"""Unit tests for CodeBuffer.

Tests the incremental code buffering and executable prefix detection without LLM calls.
"""

import pytest
from playbooks.execution.incremental_code_buffer import CodeBuffer


class TestCodeBuffer:
    """Test suite for CodeBuffer."""

    @pytest.fixture
    def buffer(self):
        """Create a fresh CodeBuffer for each test."""
        return CodeBuffer()

    def test_simple_complete_statement(self, buffer):
        """Test that a simple complete statement is detected as executable."""
        buffer.add_chunk("x = 10\n")

        prefix = buffer.get_executable_prefix()

        assert prefix == "x = 10"

    def test_incomplete_statement_returns_none(self, buffer):
        """Test that incomplete statements return None."""
        buffer.add_chunk("x = (1 + 2")

        prefix = buffer.get_executable_prefix()

        assert prefix is None

    def test_incomplete_statement_becomes_complete(self, buffer):
        """Test that incomplete statement becomes executable when completed."""
        buffer.add_chunk("x = (1 + 2")
        assert buffer.get_executable_prefix() is None

        buffer.add_chunk(" + 3)\n")

        prefix = buffer.get_executable_prefix()
        assert prefix is not None
        assert "x = (1 + 2 + 3)" in prefix

    def test_multiple_complete_statements(self, buffer):
        """Test multiple complete statements are all returned."""
        buffer.add_chunk("x = 10\n")
        buffer.add_chunk("y = 20\n")
        buffer.add_chunk("z = 30\n")

        prefix = buffer.get_executable_prefix()

        assert "x = 10" in prefix
        assert "y = 20" in prefix
        assert "z = 30" in prefix

    def test_consume_prefix_removes_from_buffer(self, buffer):
        """Test that consuming a prefix removes it from the buffer."""
        buffer.add_chunk("x = 10\n")
        buffer.add_chunk("y = 20\n")

        prefix = buffer.get_executable_prefix()
        buffer.consume_prefix(prefix)

        # Buffer should be empty after consuming all executable code
        assert buffer.get_buffer().strip() == ""

    def test_consume_partial_leaves_remainder(self, buffer):
        """Test that consuming part of buffer leaves the rest."""
        buffer.add_chunk("x = 10\n")
        buffer.add_chunk("y = (1 + 2")

        prefix = buffer.get_executable_prefix()
        assert prefix == "x = 10"

        buffer.consume_prefix(prefix)

        # y assignment should still be in buffer
        assert "y = (1 + 2" in buffer.get_buffer()

    def test_nested_for_loop_from_spec(self, buffer):
        """Test the exact nested loop example from the specification."""
        buffer.add_chunk("for i in range(3):\n")
        buffer.add_chunk("  for j in range(2):\n")
        buffer.add_chunk("    if i < j:\n")
        buffer.add_chunk("      print('less')\n")
        buffer.add_chunk("      print('hello')\n")
        buffer.add_chunk("    else:\n")
        buffer.add_chunk("      print('more')\n")
        buffer.add_chunk("  print('j done')\n")

        # Should NOT be executable yet - last line is indented
        assert buffer.get_executable_prefix() is None

        # Now add line with lower indent
        buffer.add_chunk("print('i done')\n")

        # Now the for loop is complete and executable
        prefix = buffer.get_executable_prefix()
        assert prefix is not None
        assert "for i in range(3):" in prefix
        assert "print('j done')" in prefix
        assert "print('i done')" not in prefix  # Not part of for loop

    def test_simple_for_loop(self, buffer):
        """Test a simple for loop."""
        buffer.add_chunk("for i in range(3):\n")
        buffer.add_chunk("  print(i)\n")

        # Not executable yet (last line is indented)
        assert buffer.get_executable_prefix() is None

        buffer.add_chunk("print('done')\n")

        # Now it's executable
        prefix = buffer.get_executable_prefix()
        assert "for i in range(3):" in prefix
        assert "print(i)" in prefix
        assert "print('done')" not in prefix

    def test_if_statement(self, buffer):
        """Test if statement completion detection."""
        buffer.add_chunk("x = 10\n")
        buffer.add_chunk("if x > 5:\n")
        buffer.add_chunk("  result = 'big'\n")

        # Not complete yet (last line indented, no dedent to close the if)
        assert buffer.get_executable_prefix() == "x = 10"

        buffer.add_chunk("else:\n")
        buffer.add_chunk("  result = 'small'\n")

        # Now we have a complete if/else (even though else block ends with indent)
        # The 'else:' at column 0 closes the if block, making it executable
        prefix = buffer.get_executable_prefix()
        assert "x = 10" in prefix
        assert "if x > 5:" in prefix
        assert "result = 'big'" in prefix
        # Note: else block is included even though it ends with indentation

        buffer.add_chunk("print(result)\n")

        # Now the full if/else is closed by the dedent
        prefix = buffer.get_executable_prefix()
        assert "if x > 5:" in prefix
        assert "else:" in prefix
        assert "result = 'small'" in prefix
        assert "print(result)" not in prefix

    def test_function_definition(self, buffer):
        """Test function definition completion detection."""
        buffer.add_chunk("def add(a, b):\n")
        buffer.add_chunk("  return a + b\n")

        # Not complete yet
        assert buffer.get_executable_prefix() is None

        buffer.add_chunk("\n")
        buffer.add_chunk("result = add(3, 4)\n")

        # Now function and call are complete
        prefix = buffer.get_executable_prefix()
        assert "def add(a, b):" in prefix
        assert "return a + b" in prefix
        assert "result = add(3, 4)" not in prefix

    def test_code_block_markers_stripped(self, buffer):
        """Test that ```python and ``` markers are stripped."""
        buffer.add_chunk("```python\n")
        buffer.add_chunk("x = 10\n")
        buffer.add_chunk("```\n")

        prefix = buffer.get_executable_prefix()

        assert prefix is not None
        assert "```" not in prefix
        assert "x = 10" in prefix

    def test_code_block_markers_at_start_only(self, buffer):
        """Test code block marker at start of buffer."""
        buffer.add_chunk("```python\n")
        buffer.add_chunk("x = 10\n")

        prefix = buffer.get_executable_prefix()

        assert prefix == "x = 10"

    def test_code_block_markers_at_end_only(self, buffer):
        """Test code block marker at end of buffer."""
        buffer.add_chunk("x = 10\n")
        buffer.add_chunk("```\n")

        prefix = buffer.get_executable_prefix()

        assert prefix == "x = 10"

    def test_comments_are_valid_python(self, buffer):
        """Test that comments are treated as valid Python."""
        buffer.add_chunk("# This is a comment\n")
        buffer.add_chunk("x = 5\n")

        prefix = buffer.get_executable_prefix()

        assert "# This is a comment" in prefix
        assert "x = 5" in prefix

    def test_empty_lines(self, buffer):
        """Test that empty lines are handled correctly."""
        buffer.add_chunk("x = 10\n")
        buffer.add_chunk("\n")
        buffer.add_chunk("y = 20\n")

        prefix = buffer.get_executable_prefix()

        assert "x = 10" in prefix
        assert "y = 20" in prefix

    def test_dollar_variable_preprocessing(self, buffer):
        """Test that $variable syntax is handled during parsing."""
        buffer.add_chunk("$x = 10\n")

        prefix = buffer.get_executable_prefix()

        # Should return original code with $
        assert prefix == "$x = 10"

    def test_similar_variable_names(self, buffer):
        """Test $messages vs $message (similar names)."""
        buffer.add_chunk("$messages = ['msg1', 'msg2']\n")
        buffer.add_chunk("$message = 'msg1'\n")

        prefix = buffer.get_executable_prefix()

        assert "$messages" in prefix
        assert "$message" in prefix

    def test_mid_token_chunking(self, buffer):
        """Test that mid-token chunks don't cause issues."""
        buffer.add_chunk("$mes")

        # Should not try to parse yet (no newline)
        prefix = buffer.get_executable_prefix()
        # Implementation may or may not return None here,
        # but it should handle incomplete token gracefully

        buffer.add_chunk("sage = 'hello'\n")

        prefix = buffer.get_executable_prefix()
        assert prefix == "$message = 'hello'"

    def test_empty_buffer(self, buffer):
        """Test that empty buffer returns None."""
        prefix = buffer.get_executable_prefix()
        assert prefix is None

    def test_whitespace_only_buffer(self, buffer):
        """Test that whitespace-only buffer returns None."""
        buffer.add_chunk("   \n")
        buffer.add_chunk("  \n")

        prefix = buffer.get_executable_prefix()
        assert prefix is None

    def test_get_buffer_returns_full_content(self, buffer):
        """Test that get_buffer returns the full buffer."""
        buffer.add_chunk("x = 10\n")
        buffer.add_chunk("y = 20")

        content = buffer.get_buffer()

        assert "x = 10\n" in content
        assert "y = 20" in content

    def test_multiline_string_literal(self, buffer):
        """Test multiline string literal."""
        buffer.add_chunk('x = """\n')
        buffer.add_chunk("line 1\n")
        buffer.add_chunk("line 2\n")
        buffer.add_chunk('"""\n')

        prefix = buffer.get_executable_prefix()

        assert prefix is not None
        assert '"""' in prefix

    def test_incomplete_multiline_string(self, buffer):
        """Test incomplete multiline string returns None."""
        buffer.add_chunk('x = """\n')
        buffer.add_chunk("line 1\n")
        buffer.add_chunk("line 2\n")

        prefix = buffer.get_executable_prefix()

        assert prefix is None

    def test_single_line_with_trailing_incomplete(self, buffer):
        """Test complete line followed by incomplete code."""
        buffer.add_chunk("x = 10\n")
        buffer.add_chunk("y = (1 +")

        prefix = buffer.get_executable_prefix()

        assert prefix == "x = 10"

    def test_multiple_statements_on_same_line(self, buffer):
        """Test multiple statements separated by semicolons."""
        buffer.add_chunk("x = 10; y = 20; z = 30\n")

        prefix = buffer.get_executable_prefix()

        assert "x = 10; y = 20; z = 30" in prefix

    def test_await_statement(self, buffer):
        """Test await statement is handled."""
        buffer.add_chunk('await Step("TEST:01:EXE")\n')

        prefix = buffer.get_executable_prefix()

        assert prefix == 'await Step("TEST:01:EXE")'

    def test_incomplete_function_call(self, buffer):
        """Test incomplete function call."""
        buffer.add_chunk('await Step("TEST:01')

        prefix = buffer.get_executable_prefix()

        assert prefix is None

    def test_class_definition(self, buffer):
        """Test class definition completion."""
        buffer.add_chunk("class MyClass:\n")
        buffer.add_chunk("  def __init__(self):\n")
        buffer.add_chunk("    self.x = 10\n")

        # Not complete yet
        assert buffer.get_executable_prefix() is None

        buffer.add_chunk("\n")
        buffer.add_chunk("obj = MyClass()\n")

        prefix = buffer.get_executable_prefix()
        assert "class MyClass:" in prefix
        assert "obj = MyClass()" not in prefix

    def test_try_except_block(self, buffer):
        """Test try-except block completion."""
        buffer.add_chunk("try:\n")
        buffer.add_chunk("  x = 1 / 0\n")
        buffer.add_chunk("except:\n")
        buffer.add_chunk("  x = 0\n")

        # Not complete yet (last line indented)
        assert buffer.get_executable_prefix() is None

        buffer.add_chunk("print(x)\n")

        prefix = buffer.get_executable_prefix()
        assert "try:" in prefix
        assert "except:" in prefix
        assert "print(x)" not in prefix

    def test_list_comprehension(self, buffer):
        """Test list comprehension."""
        buffer.add_chunk("numbers = [i for i in range(10)]\n")

        prefix = buffer.get_executable_prefix()

        assert "numbers = [i for i in range(10)]" in prefix

    def test_dict_literal_multiline(self, buffer):
        """Test multiline dict literal."""
        buffer.add_chunk("data = {\n")
        buffer.add_chunk("  'key1': 'value1',\n")
        buffer.add_chunk("  'key2': 'value2'\n")
        buffer.add_chunk("}\n")

        prefix = buffer.get_executable_prefix()

        assert "data = {" in prefix
        assert "'key1': 'value1'" in prefix

    def test_list_literal_multiline(self, buffer):
        """Test multiline list literal."""
        buffer.add_chunk("items = [\n")
        buffer.add_chunk("  'item1',\n")
        buffer.add_chunk("  'item2',\n")
        buffer.add_chunk("  'item3'\n")
        buffer.add_chunk("]\n")

        prefix = buffer.get_executable_prefix()

        assert "items = [" in prefix
        assert "'item1'" in prefix

    def test_comment_after_statement(self, buffer):
        """Test comment on same line as statement."""
        buffer.add_chunk("x = 10  # this is x\n")

        prefix = buffer.get_executable_prefix()

        assert "x = 10" in prefix

    def test_real_llm_generated_code_pattern(self, buffer):
        """Test a realistic LLM-generated code pattern."""
        buffer.add_chunk("# execution_id: 3\n")
        buffer.add_chunk("# recap: Starting game\n")
        buffer.add_chunk("# plan: Welcome players\n")
        buffer.add_chunk("\n")
        buffer.add_chunk('await Step("GameRoom:01:QUE")\n')

        prefix = buffer.get_executable_prefix()

        assert prefix is not None
        assert "# execution_id: 3" in prefix
        assert 'await Step("GameRoom:01:QUE")' in prefix

    def test_consume_updates_buffer_correctly(self, buffer):
        """Test that consume_prefix correctly updates the buffer."""
        buffer.add_chunk("x = 10\n")
        buffer.add_chunk("y = 20\n")
        buffer.add_chunk("z = (1 + 2")

        prefix = buffer.get_executable_prefix()
        assert "x = 10" in prefix
        assert "y = 20" in prefix

        buffer.consume_prefix(prefix)

        remaining = buffer.get_buffer()
        assert "x = 10" not in remaining
        assert "y = 20" not in remaining
        assert "z = (1 + 2" in remaining
