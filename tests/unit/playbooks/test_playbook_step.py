"""Tests for playbook_step module."""

from unittest.mock import Mock, patch

from playbooks.playbook_step import PlaybookStep, PlaybookStepCollection


class TestPlaybookStep:
    """Test PlaybookStep class."""

    def test_playbook_step_initialization(self):
        """Test PlaybookStep initialization."""
        step = PlaybookStep(
            line_number="01",
            step_type="YLD",
            content="Hello world",
            raw_text="01:YLD: Hello world",
            source_line_number=10,
        )

        assert step.line_number == "01"
        assert step.step_type == "YLD"
        assert step.content == "Hello world"
        assert step.raw_text == "01:YLD: Hello world"
        assert step.source_line_number == 10

        # Check DAG properties are initialized
        assert step.next_steps == []
        assert step.parent_step is None
        assert step.child_steps == []
        assert step.is_in_loop is False
        assert step.loop_entry is None
        assert step.else_step is None
        assert step.cnd_step is None

    def test_from_text_valid_step(self):
        """Test creating PlaybookStep from valid text."""
        text = "02:YLD: This is a yield step"
        step = PlaybookStep.from_text(text)

        assert step is not None
        assert step.line_number == "02"
        assert step.step_type == "YLD"
        assert step.content == "This is a yield step"
        assert step.raw_text == text

    def test_from_text_nested_line_number(self):
        """Test creating PlaybookStep with nested line number."""
        text = "02.01:EXE: Execute something"
        step = PlaybookStep.from_text(text)

        assert step is not None
        assert step.line_number == "02.01"
        assert step.step_type == "EXE"
        assert step.content == "Execute something"

    def test_from_text_no_content(self):
        """Test creating PlaybookStep without content."""
        text = "03:RET"
        step = PlaybookStep.from_text(text)

        assert step is not None
        assert step.line_number == "03"
        assert step.step_type == "RET"
        assert step.content == ""

    def test_from_text_with_leading_colon_in_content(self):
        """Test creating PlaybookStep with leading colon in content."""
        text = "04:CND:: If condition is true"
        step = PlaybookStep.from_text(text)

        assert step is not None
        assert step.line_number == "04"
        assert step.step_type == "CND"
        # The code only removes one leading colon if present
        assert step.content == ": If condition is true"

    def test_from_text_with_single_leading_colon(self):
        """Test creating PlaybookStep with single leading colon in content."""
        text = "04:CND: If condition is true"
        step = PlaybookStep.from_text(text)

        assert step is not None
        assert step.line_number == "04"
        assert step.step_type == "CND"
        assert step.content == "If condition is true"

    def test_from_text_empty_string(self):
        """Test from_text with empty string."""
        step = PlaybookStep.from_text("")
        assert step is None

    def test_from_text_invalid_format(self):
        """Test from_text with invalid format."""
        step = PlaybookStep.from_text("This is not a valid step")
        assert step is None

    def test_from_text_exception_handling(self):
        """Test from_text handles exceptions gracefully."""
        # The exception handling is actually in the try block around the group access
        # Let's make the match return an object that raises on group()
        mock_match_obj = Mock()
        mock_match_obj.group.side_effect = Exception("Parse error")

        with patch("playbooks.playbook_step.re.match") as mock_match:
            mock_match.return_value = mock_match_obj
            step = PlaybookStep.from_text("01:YLD: Test")
            assert step is None

    def test_is_yield(self):
        """Test is_yield method."""
        step_yield = PlaybookStep("01", "YLD", "content", "raw")
        step_other = PlaybookStep("02", "EXE", "content", "raw")

        assert step_yield.is_yield() is True
        assert step_other.is_yield() is False

    def test_is_return(self):
        """Test is_return method."""
        step_return = PlaybookStep("01", "RET", "content", "raw")
        step_other = PlaybookStep("02", "YLD", "content", "raw")

        assert step_return.is_return() is True
        assert step_other.is_return() is False

    def test_is_loop(self):
        """Test is_loop method."""
        step_loop = PlaybookStep("01", "LOP", "content", "raw")
        step_other = PlaybookStep("02", "YLD", "content", "raw")

        assert step_loop.is_loop() is True
        assert step_other.is_loop() is False

    def test_is_conditional(self):
        """Test is_conditional method."""
        step_cnd = PlaybookStep("01", "CND", "content", "raw")
        step_other = PlaybookStep("02", "YLD", "content", "raw")

        assert step_cnd.is_conditional() is True
        assert step_other.is_conditional() is False

    def test_is_else(self):
        """Test is_else method."""
        step_else = PlaybookStep("01", "ELS", "content", "raw")
        step_other = PlaybookStep("02", "YLD", "content", "raw")

        assert step_else.is_else() is True
        assert step_other.is_else() is False

    def test_dag_navigation(self):
        """Test DAG navigation properties can be set."""
        parent = PlaybookStep("01", "YLD", "parent", "raw")
        child1 = PlaybookStep("01.01", "EXE", "child1", "raw")
        child2 = PlaybookStep("01.02", "EXE", "child2", "raw")
        next_step = PlaybookStep("02", "YLD", "next", "raw")

        parent.child_steps = [child1, child2]
        parent.next_steps = [next_step]
        child1.parent_step = parent
        child2.parent_step = parent

        assert len(parent.child_steps) == 2
        assert parent.child_steps[0] == child1
        assert parent.child_steps[1] == child2
        assert child1.parent_step == parent
        assert child2.parent_step == parent
        assert parent.next_steps[0] == next_step

    def test_loop_properties(self):
        """Test loop-related properties."""
        loop_step = PlaybookStep("01", "LOP", "for each item", "raw")
        body_step = PlaybookStep("01.01", "YLD", "process item", "raw")

        body_step.is_in_loop = True
        body_step.loop_entry = loop_step
        loop_step.child_steps = [body_step]

        assert body_step.is_in_loop is True
        assert body_step.loop_entry == loop_step
        assert loop_step.child_steps[0] == body_step

    def test_conditional_properties(self):
        """Test conditional-related properties."""
        cnd_step = PlaybookStep("01", "CND", "if condition", "raw")
        then_step = PlaybookStep("01.01", "YLD", "then action", "raw")
        else_step = PlaybookStep("01.02", "ELS", "else action", "raw")

        cnd_step.child_steps = [then_step]
        cnd_step.else_step = else_step
        then_step.cnd_step = cnd_step
        else_step.cnd_step = cnd_step

        assert cnd_step.else_step == else_step
        assert then_step.cnd_step == cnd_step
        assert else_step.cnd_step == cnd_step

    def test_get_parent_line_number(self):
        """Test get_parent_line_number method."""
        # Top-level step should return None
        top_level = PlaybookStep("01", "YLD", "content", "raw")
        assert top_level.get_parent_line_number() is None

        # Single nested level
        nested_1 = PlaybookStep("01.01", "EXE", "content", "raw")
        assert nested_1.get_parent_line_number() == "01"

        # Double nested level
        nested_2 = PlaybookStep("01.02.03", "EXE", "content", "raw")
        assert nested_2.get_parent_line_number() == "01.02"

        # Triple nested level
        nested_3 = PlaybookStep("01.02.03.04", "EXE", "content", "raw")
        assert nested_3.get_parent_line_number() == "01.02.03"

    def test_string_representations(self):
        """Test __str__ and __repr__ methods."""
        step = PlaybookStep("01.02", "YLD", "Hello world", "01.02:YLD: Hello world")

        # Test __str__
        str_repr = str(step)
        assert str_repr == "01.02:YLD: Hello world"

        # Test __repr__
        repr_str = repr(step)
        assert repr_str == "PlaybookStep(01.02, YLD, Hello world)"

    def test_execute_method(self):
        """Test execute method exists and can be called."""
        step = PlaybookStep("01", "YLD", "content", "raw")
        # Should not raise an exception
        result = step.execute()
        assert result is None


class TestPlaybookStepCollection:
    """Test PlaybookStepCollection class."""

    def test_initialization(self):
        """Test PlaybookStepCollection initialization."""
        collection = PlaybookStepCollection()

        assert collection.steps == {}
        assert collection.ordered_line_numbers == []
        assert collection.entry_point is None
        assert collection._dag_built is False

    def test_add_step_basic(self):
        """Test adding a basic step."""
        collection = PlaybookStepCollection()
        step = PlaybookStep("01", "YLD", "content", "raw")

        collection.add_step(step)

        assert "01" in collection.steps
        assert collection.steps["01"] == step
        assert "01" in collection.ordered_line_numbers
        assert collection._dag_built is False

    def test_add_multiple_steps_ordering(self):
        """Test adding multiple steps maintains correct ordering."""
        collection = PlaybookStepCollection()

        step2 = PlaybookStep("02", "YLD", "content2", "raw2")
        step1 = PlaybookStep("01", "YLD", "content1", "raw1")
        step3 = PlaybookStep("03", "YLD", "content3", "raw3")

        # Add out of order
        collection.add_step(step2)
        collection.add_step(step1)
        collection.add_step(step3)

        assert collection.ordered_line_numbers == ["01", "02", "03"]

    def test_add_nested_steps_ordering(self):
        """Test adding nested steps maintains correct ordering."""
        collection = PlaybookStepCollection()

        steps = [
            PlaybookStep("01", "YLD", "content1", "raw1"),
            PlaybookStep("01.01", "EXE", "content1.1", "raw1.1"),
            PlaybookStep("01.02", "EXE", "content1.2", "raw1.2"),
            PlaybookStep("02", "YLD", "content2", "raw2"),
            PlaybookStep("02.01", "EXE", "content2.1", "raw2.1"),
        ]

        # Add in random order
        for step in [steps[3], steps[0], steps[4], steps[1], steps[2]]:
            collection.add_step(step)

        expected_order = ["01", "01.01", "01.02", "02", "02.01"]
        assert collection.ordered_line_numbers == expected_order

    def test_compare_line_numbers(self):
        """Test _compare_line_numbers method."""
        collection = PlaybookStepCollection()

        # Same numbers
        assert collection._compare_line_numbers("01", "01") == 0

        # Different single level
        assert collection._compare_line_numbers("01", "02") == -1
        assert collection._compare_line_numbers("02", "01") == 1

        # Single vs nested - single comes first
        assert collection._compare_line_numbers("01", "01.01") == -1
        assert collection._compare_line_numbers("01.01", "01") == 1

        # Different nested levels
        assert collection._compare_line_numbers("01.01", "01.02") == -1
        assert collection._compare_line_numbers("01.02", "01.01") == 1

        # Different nesting depths
        assert collection._compare_line_numbers("01.01", "01.01.01") == -1
        assert collection._compare_line_numbers("01.01.01", "01.01") == 1

    def test_get_next_line_number_at_same_level(self):
        """Test _get_next_line_number_at_same_level method."""
        collection = PlaybookStepCollection()

        # Top level
        assert collection._get_next_line_number_at_same_level("01") == "02"
        assert collection._get_next_line_number_at_same_level("09") == "10"

        # Nested level
        assert collection._get_next_line_number_at_same_level("01.01") == "01.02"
        assert collection._get_next_line_number_at_same_level("01.09") == "01.10"

        # Double nested
        assert collection._get_next_line_number_at_same_level("01.02.03") == "01.02.04"

    def test_get_step(self):
        """Test get_step method."""
        collection = PlaybookStepCollection()
        step = PlaybookStep("01", "YLD", "content", "raw")
        collection.add_step(step)

        assert collection.get_step("01") == step
        assert collection.get_step("99") is None

    def test_get_all_steps(self):
        """Test get_all_steps method."""
        collection = PlaybookStepCollection()

        step1 = PlaybookStep("01", "YLD", "content1", "raw1")
        step2 = PlaybookStep("02", "YLD", "content2", "raw2")

        collection.add_step(step2)
        collection.add_step(step1)

        all_steps = collection.get_all_steps()
        assert len(all_steps) == 2
        assert all_steps[0] == step1  # Should be in order
        assert all_steps[1] == step2

    def test_len_and_iter(self):
        """Test __len__ and __iter__ methods."""
        collection = PlaybookStepCollection()

        step1 = PlaybookStep("01", "YLD", "content1", "raw1")
        step2 = PlaybookStep("02", "YLD", "content2", "raw2")

        collection.add_step(step1)
        collection.add_step(step2)

        assert len(collection) == 2

        # Test iteration
        steps_list = list(collection)
        assert len(steps_list) == 2
        assert steps_list[0] == step1
        assert steps_list[1] == step2

    def test_build_dag_basic_sequence(self):
        """Test basic DAG building for sequential steps."""
        collection = PlaybookStepCollection()

        step1 = PlaybookStep("01", "YLD", "content1", "raw1")
        step2 = PlaybookStep("02", "YLD", "content2", "raw2")
        step3 = PlaybookStep("03", "YLD", "content3", "raw3")

        collection.add_step(step1)
        collection.add_step(step2)
        collection.add_step(step3)

        # Force DAG building
        collection._build_dag()

        # Check entry point
        assert collection.entry_point == step1

        # Check sequential relationships
        assert len(step1.next_steps) == 1
        assert step1.next_steps[0] == step2
        assert len(step2.next_steps) == 1
        assert step2.next_steps[0] == step3
        assert len(step3.next_steps) == 0  # Last step has no next

        assert collection._dag_built is True

    def test_build_dag_parent_child_relationships(self):
        """Test DAG building creates parent-child relationships."""
        collection = PlaybookStepCollection()

        parent = PlaybookStep("01", "YLD", "parent", "raw_parent")
        child1 = PlaybookStep("01.01", "EXE", "child1", "raw_child1")
        child2 = PlaybookStep("01.02", "EXE", "child2", "raw_child2")

        collection.add_step(parent)
        collection.add_step(child1)
        collection.add_step(child2)

        collection._build_dag()

        # Check parent-child relationships
        assert child1.parent_step == parent
        assert child2.parent_step == parent
        assert len(parent.child_steps) == 2
        assert child1 in parent.child_steps
        assert child2 in parent.child_steps

    def test_build_dag_loop_relationships(self):
        """Test DAG building for loop structures."""
        collection = PlaybookStepCollection()

        loop_step = PlaybookStep("01", "LOP", "for each item", "raw_loop")
        body_step = PlaybookStep("01.01", "YLD", "process item", "raw_body")
        after_loop = PlaybookStep("02", "YLD", "after loop", "raw_after")

        collection.add_step(loop_step)
        collection.add_step(body_step)
        collection.add_step(after_loop)

        collection._build_dag()

        # Check loop properties
        assert body_step.is_in_loop is True
        assert body_step.loop_entry == loop_step

        # Check loop navigation
        assert len(loop_step.next_steps) >= 1
        assert loop_step.next_steps[0] == body_step

        # Body step should go back to loop
        assert len(body_step.next_steps) == 1
        assert body_step.next_steps[0] == loop_step

    def test_build_dag_conditional_with_else(self):
        """Test DAG building for conditional with else."""
        collection = PlaybookStepCollection()

        cnd_step = PlaybookStep("01", "CND", "if condition", "raw_cnd")
        then_step = PlaybookStep("01.01", "YLD", "then action", "raw_then")
        else_step = PlaybookStep("02", "ELS", "else action", "raw_else")
        after_step = PlaybookStep("03", "YLD", "after conditional", "raw_after")

        collection.add_step(cnd_step)
        collection.add_step(then_step)
        collection.add_step(else_step)
        collection.add_step(after_step)

        collection._build_dag()

        # Check conditional relationships
        assert cnd_step.else_step == else_step
        assert else_step.cnd_step == cnd_step

    def test_build_dag_conditional_without_else(self):
        """Test DAG building for conditional without else."""
        collection = PlaybookStepCollection()

        cnd_step = PlaybookStep("01", "CND", "if condition", "raw_cnd")
        then_step = PlaybookStep("01.01", "YLD", "then action", "raw_then")
        after_step = PlaybookStep("02", "YLD", "after conditional", "raw_after")

        collection.add_step(cnd_step)
        collection.add_step(then_step)
        collection.add_step(after_step)

        collection._build_dag()

        # Check that no else relationship exists
        assert cnd_step.else_step is None

    def test_get_next_step_basic_sequence(self):
        """Test get_next_step for basic sequence."""
        collection = PlaybookStepCollection()

        step1 = PlaybookStep("01", "YLD", "content1", "raw1")
        step2 = PlaybookStep("02", "YLD", "content2", "raw2")

        collection.add_step(step1)
        collection.add_step(step2)

        # Test navigation
        next_step = collection.get_next_step("01")
        assert next_step == step2

        # Last step should return None
        next_step = collection.get_next_step("02")
        assert next_step is None

        # Non-existent step should return None
        next_step = collection.get_next_step("99")
        assert next_step is None

    def test_get_next_step_in_loop(self):
        """Test get_next_step behavior within loops."""
        collection = PlaybookStepCollection()

        loop_step = PlaybookStep("01", "LOP", "for each item", "raw_loop")
        body1 = PlaybookStep("01.01", "YLD", "process1", "raw_body1")
        body2 = PlaybookStep("01.02", "YLD", "process2", "raw_body2")
        after_loop = PlaybookStep("02", "YLD", "after loop", "raw_after")

        collection.add_step(loop_step)
        collection.add_step(body1)
        collection.add_step(body2)
        collection.add_step(after_loop)

        # Test navigation within loop
        next_step = collection.get_next_step("01.01")
        assert next_step == body2

        # Last step in loop should return to loop entry (based on actual implementation)
        collection._build_dag()  # Force DAG building
        next_step = collection.get_next_step("01.02")
        assert next_step == loop_step

    def test_empty_collection_operations(self):
        """Test operations on empty collection."""
        collection = PlaybookStepCollection()

        assert len(collection) == 0
        assert list(collection) == []
        assert collection.get_step("01") is None
        assert collection.get_next_step("01") is None
        assert collection.get_all_steps() == []

        # DAG building on empty collection should not crash
        collection._build_dag()
        assert collection.entry_point is None

    def test_dag_rebuilding_after_adding_steps(self):
        """Test that DAG is rebuilt when steps are added."""
        collection = PlaybookStepCollection()

        step1 = PlaybookStep("01", "YLD", "content1", "raw1")
        collection.add_step(step1)

        # Force initial DAG build
        collection._build_dag()
        assert collection._dag_built is True

        # Adding another step should reset DAG built flag
        step2 = PlaybookStep("02", "YLD", "content2", "raw2")
        collection.add_step(step2)
        assert collection._dag_built is False

    def test_find_last_step_in_loop_edge_cases(self):
        """Test _find_last_step_in_loop with edge cases."""
        collection = PlaybookStepCollection()

        # Loop with no children
        loop_step = PlaybookStep("01", "LOP", "empty loop", "raw")
        collection.add_step(loop_step)

        result = collection._find_last_step_in_loop(loop_step)
        assert result is None

    def test_find_step_after_loop_edge_cases(self):
        """Test _find_step_after_loop with edge cases."""
        collection = PlaybookStepCollection()

        loop_step = PlaybookStep("01", "LOP", "loop", "raw")
        collection.add_step(loop_step)

        # Loop step not in ordered list (shouldn't happen but test robustness)
        result = collection._find_step_after_loop(
            PlaybookStep("99", "LOP", "unknown", "raw")
        )
        assert result is None

    def test_mark_descendants_in_loop(self):
        """Test recursive marking of descendants in loop."""
        collection = PlaybookStepCollection()

        loop_step = PlaybookStep("01", "LOP", "loop", "raw")
        child = PlaybookStep("01.01", "YLD", "child", "raw")
        grandchild = PlaybookStep("01.01.01", "EXE", "grandchild", "raw")

        collection.add_step(loop_step)
        collection.add_step(child)
        collection.add_step(grandchild)

        collection._build_dag()

        # Both child and grandchild should be marked as in loop
        assert child.is_in_loop is True
        assert child.loop_entry == loop_step
        assert grandchild.is_in_loop is True
        assert grandchild.loop_entry == loop_step

    def test_find_last_step_in_conditional_edge_cases(self):
        """Test _find_last_step_in_conditional with edge cases."""
        collection = PlaybookStepCollection()

        # Conditional with no children
        cnd_step = PlaybookStep("01", "CND", "empty condition", "raw")
        collection.add_step(cnd_step)

        result = collection._find_last_step_in_conditional(cnd_step)
        assert result is None

    def test_duplicate_step_line_numbers(self):
        """Test handling of duplicate line numbers."""
        collection = PlaybookStepCollection()

        step1 = PlaybookStep("01", "YLD", "first", "raw1")
        step2 = PlaybookStep("01", "EXE", "second", "raw2")

        collection.add_step(step1)
        collection.add_step(step2)

        # Second step should replace first
        assert collection.steps["01"] == step2
        assert len(collection.ordered_line_numbers) == 1
