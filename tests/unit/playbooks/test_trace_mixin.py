from playbooks.trace_mixin import TraceItem, TraceMixin, TraceWalker


class TestTraceItem:
    def test_initialization(self):
        # Test with string item
        item = TraceItem("test item")
        assert item.item == "test item"
        assert item.metadata is None

        # Test with metadata
        metadata = {"key": "value"}
        item_with_metadata = TraceItem("test item", metadata)
        assert item_with_metadata.item == "test item"
        assert item_with_metadata.metadata == metadata

    def test_repr(self):
        item = TraceItem("test item")
        # The actual implementation wraps strings in quotes
        assert repr(item) == "'test item'"

        # Test with TraceMixin object
        class MockTraceMixin(TraceMixin):
            def __repr__(self):
                return "MockTraceMixin"

        mock_trace = MockTraceMixin()
        item_with_trace = TraceItem(mock_trace)
        assert repr(item_with_trace) == "MockTraceMixin"

    def test_str(self):
        item = TraceItem("test item")
        assert str(item) == "test item"

        # Test with TraceMixin object
        class MockTraceMixin(TraceMixin):
            def __str__(self):
                return "MockTraceMixin String"

        mock_trace = MockTraceMixin()
        item_with_trace = TraceItem(mock_trace)
        assert str(item_with_trace) == "MockTraceMixin String"


class TestTraceMixin:
    def test_initialization(self):
        trace = TraceMixin()
        assert trace._trace_items == []
        assert trace._trace_summary == "Empty"

    def test_trace_with_string(self):
        trace = TraceMixin()
        trace.trace("test trace")

        assert len(trace._trace_items) == 1
        assert trace._trace_items[0].item == "test trace"
        assert trace._trace_items[0].metadata is None

    def test_trace_with_metadata(self):
        trace = TraceMixin()
        metadata = {"key": "value"}
        trace.trace("test trace", metadata)

        assert len(trace._trace_items) == 1
        assert trace._trace_items[0].item == "test trace"
        assert trace._trace_items[0].metadata == metadata

    def test_trace_with_trace_mixin(self):
        parent_trace = TraceMixin()
        child_trace = TraceMixin()

        parent_trace.trace(child_trace)

        assert len(parent_trace._trace_items) == 1
        assert parent_trace._trace_items[0].item == child_trace

    def test_refresh_trace_summary(self):
        trace = TraceMixin()
        trace.trace("test trace")

        # Mock to_trace method
        original_to_trace = trace.to_trace
        trace.to_trace = lambda depth=1: "Mocked trace summary"

        trace.refresh_trace_summary()
        assert trace._trace_summary == "Mocked trace summary"

        # Restore original method
        trace.to_trace = original_to_trace

    def test_str(self):
        trace = TraceMixin()
        trace._trace_summary = "Test summary"
        assert str(trace) == "Test summary"

    def test_to_trace_empty(self):
        trace = TraceMixin()
        # The actual implementation returns an empty string for empty trace
        assert trace.to_trace() == ""

    def test_to_trace_with_strings(self):
        trace = TraceMixin()
        trace.trace("item 1")
        trace.trace("item 2")

        expected = "  - item 1\n  - item 2"
        assert trace.to_trace() == expected

    def test_to_trace_with_nested_trace(self):
        parent = TraceMixin()
        child = TraceMixin()
        child.trace("child item")

        parent.trace(child)
        parent.trace("parent item")

        # The exact format depends on the __repr__ implementation
        result = parent.to_trace()
        assert "child item" in result
        assert "parent item" in result


class TestTraceWalker:
    def test_walk_with_trace_mixin(self):
        trace = TraceMixin()
        trace.trace("item 1")
        trace.trace("item 2")

        visited_items = []

        def visitor(item):
            visited_items.append(item.item)

        TraceWalker.walk(trace, visitor)

        assert visited_items == ["item 1", "item 2"]

    def test_walk_with_nested_trace(self):
        parent = TraceMixin()
        child = TraceMixin()
        child.trace("child item 1")
        child.trace("child item 2")

        parent.trace(child)
        parent.trace("parent item")

        visited_items = []

        def visitor(item):
            visited_items.append(item.item)

        TraceWalker.walk(parent, visitor)

        # Should visit child first, then its items, then parent item
        assert len(visited_items) == 4
        assert child in visited_items
        assert "child item 1" in visited_items
        assert "child item 2" in visited_items
        assert "parent item" in visited_items

    def test_walk_with_trace_item(self):
        trace_item = TraceItem("test item")

        visited_items = []

        def visitor(item):
            visited_items.append(item.item)

        TraceWalker.walk(trace_item, visitor)

        assert visited_items == ["test item"]
