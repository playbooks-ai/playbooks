import uuid
from unittest.mock import MagicMock, patch

from playbooks.trace_mixin import StringTrace, TraceMixin, TraceWalker, indent
from playbooks.types import AgentResponseChunk


class TestIndent:
    def test_indent_single_line(self):
        """Test indenting a single line string."""
        result = indent("test", 2)
        assert result == "    test"

    def test_indent_multiple_lines(self):
        """Test indenting a multi-line string."""
        result = indent("line1\nline2", 1)
        assert result == "  line1\n  line2"

    def test_indent_zero_level(self):
        """Test indenting with zero level."""
        result = indent("test", 0)
        assert result == "test"


class TestTraceMixin:
    def test_initialization(self):
        """Test TraceMixin initialization."""
        with patch(
            "uuid.uuid4", return_value=uuid.UUID("12345678-1234-5678-1234-567812345678")
        ):
            trace = TraceMixin()
            assert trace._trace_id == "12345678-1234-5678-1234-567812345678"
            assert trace._trace_metadata == {}
            assert trace._trace_items == []

    def test_trace_with_string(self):
        """Test adding a string to trace."""
        trace = TraceMixin()
        trace.trace("test message")

        assert len(trace._trace_items) == 1
        assert isinstance(trace._trace_items[0], StringTrace)
        assert trace._trace_items[0].message == "test message"
        assert trace._trace_items[0]._trace_metadata["parent_id"] == trace._trace_id

    def test_trace_with_trace_mixin(self):
        """Test adding a TraceMixin instance to trace."""
        parent = TraceMixin()
        child = TraceMixin()

        parent.trace(child)

        assert len(parent._trace_items) == 1
        assert parent._trace_items[0] == child
        assert child._trace_metadata["parent_id"] == parent._trace_id

    def test_trace_with_metadata(self):
        """Test adding trace with metadata."""
        trace = TraceMixin()
        child = TraceMixin()

        trace.trace(child, metadata={"key": "value"})

        assert child._trace_metadata["parent_id"] == trace._trace_id

    def test_to_trace(self):
        """Test converting trace to list representation."""
        trace = TraceMixin()
        trace.trace("message1")
        trace.trace("message2")

        result = trace.to_trace()

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == "message1"
        assert result[1] == "message2"

    def test_yield_trace(self):
        """Test yielding trace as AgentResponseChunk."""
        trace = TraceMixin()
        trace.trace("test message")

        chunks = list(trace.yield_trace())

        assert len(chunks) == 1
        assert isinstance(chunks[0], AgentResponseChunk)
        assert chunks[0].trace == ["test message"]


class TestStringTrace:
    def test_initialization(self):
        """Test StringTrace initialization."""
        trace = StringTrace("test message")

        assert trace.message == "test message"
        assert isinstance(trace, TraceMixin)

    def test_to_trace(self):
        """Test converting StringTrace to string representation."""
        trace = StringTrace("test message")

        result = trace.to_trace()

        assert result == "test message"


class TestTraceWalker:
    def test_walk_with_empty_trace(self):
        """Test walking an empty trace."""
        trace = TraceMixin()
        visitor = MagicMock()

        TraceWalker.walk(trace, visitor)

        visitor.assert_not_called()

    def test_walk_with_nested_traces(self):
        """Test walking nested traces."""
        root = TraceMixin()
        child1 = TraceMixin()
        child2 = TraceMixin()
        grandchild = TraceMixin()

        root.trace(child1)
        root.trace(child2)
        child1.trace(grandchild)

        visited = []

        def visitor(item):
            visited.append(item)

        TraceWalker.walk(root, visitor)

        assert len(visited) == 3
        assert child1 in visited
        assert child2 in visited
        assert grandchild in visited

    def test_walk_with_string_traces(self):
        """Test walking traces with string items."""
        root = TraceMixin()
        root.trace("message1")
        root.trace("message2")

        visited = []

        def visitor(item):
            visited.append(item)

        TraceWalker.walk(root, visitor)

        assert len(visited) == 2
        assert all(isinstance(item, StringTrace) for item in visited)
        assert visited[0].message == "message1"
        assert visited[1].message == "message2"

    def test_walk_with_non_trace_item(self):
        """Test walking with a non-TraceMixin item."""
        visitor = MagicMock()

        # Should not raise an exception
        TraceWalker.walk("not a trace", visitor)

        visitor.assert_not_called()
