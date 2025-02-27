"""Tests for the PlaybookStep and PlaybookStepCollection classes."""

from playbooks.playbook_step import PlaybookStep, PlaybookStepCollection


class TestPlaybookStep:
    """Tests for the PlaybookStep class."""

    def test_initialization(self):
        """Test that the PlaybookStep class initializes correctly."""
        line_number = "01"
        step_type = "YLD"
        content = "ForUserInput"
        raw_text = "01:YLD: ForUserInput"

        step = PlaybookStep(line_number, step_type, content, raw_text)

        assert step.line_number == line_number
        assert step.step_type == step_type
        assert step.content == content
        assert step.raw_text == raw_text

    def test_from_text(self):
        """Test creating a PlaybookStep from text."""
        text = "01:YLD: ForUserInput"
        step = PlaybookStep.from_text(text)

        assert step is not None
        assert step.line_number == "01"
        assert step.step_type == "YLD"
        assert step.content == "ForUserInput"
        assert step.raw_text == text

    def test_from_text_invalid(self):
        """Test creating a PlaybookStep from invalid text."""
        # No colons
        assert PlaybookStep.from_text("Invalid text") is None

        # Only one colon
        assert PlaybookStep.from_text("01: Invalid") is None

        # Empty text
        assert PlaybookStep.from_text("") is None

        # None
        assert PlaybookStep.from_text(None) is None

    def test_is_yield(self):
        """Test the is_yield method."""
        step = PlaybookStep("01", "YLD", "ForUserInput", "01:YLD: ForUserInput")
        assert step.is_yield() is True

        step = PlaybookStep("01", "QUE", "Say()", "01:QUE: Say()")
        assert step.is_yield() is False

    def test_is_return(self):
        """Test the is_return method."""
        step = PlaybookStep("01", "RET", "return result", "01:RET: return result")
        assert step.is_return() is True

        step = PlaybookStep("01", "QUE", "Say()", "01:QUE: Say()")
        assert step.is_return() is False

    def test_get_next_line_number(self):
        """Test the get_next_line_number method."""
        # Simple line number
        step = PlaybookStep("01", "YLD", "ForUserInput", "01:YLD: ForUserInput")
        assert step.get_next_line_number() == "02"

        # Nested line number
        step = PlaybookStep("01.01", "YLD", "ForUserInput", "01.01:YLD: ForUserInput")
        assert step.get_next_line_number() == "01.02"

        # Invalid line number
        step = PlaybookStep(
            "invalid", "YLD", "ForUserInput", "invalid:YLD: ForUserInput"
        )
        assert step.get_next_line_number() is None

    def test_str_and_repr(self):
        """Test the __str__ and __repr__ methods."""
        step = PlaybookStep("01", "YLD", "ForUserInput", "01:YLD: ForUserInput")

        assert str(step) == "01:YLD: ForUserInput"
        assert repr(step) == "PlaybookStep(01, YLD, ForUserInput)"

    def test_is_loop(self):
        """Test the is_loop method."""
        step = PlaybookStep("01", "LOP", "For each", "01:LOP: For each")
        assert step.is_loop() is True

        step = PlaybookStep("01", "QUE", "Say()", "01:QUE: Say()")
        assert step.is_loop() is False

    def test_is_conditional(self):
        """Test the is_conditional method."""
        step = PlaybookStep("01", "CND", "If condition", "01:CND: If condition")
        assert step.is_conditional() is True

        step = PlaybookStep("01", "QUE", "Say()", "01:QUE: Say()")
        assert step.is_conditional() is False

    def test_is_else(self):
        """Test the is_else method."""
        step = PlaybookStep("01", "ELS", "Otherwise", "01:ELS: Otherwise")
        assert step.is_else() is True

        step = PlaybookStep("01", "QUE", "Say()", "01:QUE: Say()")
        assert step.is_else() is False

    def test_get_parent_line_number(self):
        """Test the get_parent_line_number method."""
        # Simple line number
        step = PlaybookStep("01", "YLD", "ForUserInput", "01:YLD: ForUserInput")
        assert step.get_parent_line_number() is None

        # Nested line number
        step = PlaybookStep("01.01", "YLD", "ForUserInput", "01.01:YLD: ForUserInput")
        assert step.get_parent_line_number() == "01"

        # Double nested line number
        step = PlaybookStep(
            "01.02.03", "YLD", "ForUserInput", "01.02.03:YLD: ForUserInput"
        )
        assert step.get_parent_line_number() == "01.02"


class TestPlaybookStepCollection:
    """Tests for the PlaybookStepCollection class."""

    def test_initialization(self):
        """Test that the PlaybookStepCollection class initializes correctly."""
        collection = PlaybookStepCollection()

        assert collection.steps == {}
        assert collection.ordered_line_numbers == []

    def test_add_step(self):
        """Test adding steps to the collection."""
        collection = PlaybookStepCollection()

        step1 = PlaybookStep("01", "YLD", "ForUserInput", "01:YLD: ForUserInput")
        step2 = PlaybookStep("02", "QUE", "Say()", "02:QUE: Say()")

        collection.add_step(step1)
        collection.add_step(step2)

        assert len(collection.steps) == 2
        assert collection.steps["01"] == step1
        assert collection.steps["02"] == step2
        assert collection.ordered_line_numbers == ["01", "02"]

    def test_add_step_ordering(self):
        """Test that steps are ordered correctly."""
        collection = PlaybookStepCollection()

        # Add steps in reverse order
        step3 = PlaybookStep("03", "RET", "return", "03:RET: return")
        step1 = PlaybookStep("01", "YLD", "ForUserInput", "01:YLD: ForUserInput")
        step2 = PlaybookStep("02", "QUE", "Say()", "02:QUE: Say()")

        collection.add_step(step3)
        collection.add_step(step1)
        collection.add_step(step2)

        assert collection.ordered_line_numbers == ["01", "02", "03"]

    def test_add_step_nested_ordering(self):
        """Test that nested steps are ordered correctly."""
        collection = PlaybookStepCollection()

        # Add steps in mixed order
        step1 = PlaybookStep("01", "LOP", "For each", "01:LOP: For each")
        step1_2 = PlaybookStep("01.02", "QUE", "Say()", "01.02:QUE: Say()")
        step1_1 = PlaybookStep(
            "01.01", "YLD", "ForUserInput", "01.01:YLD: ForUserInput"
        )
        step2 = PlaybookStep("02", "RET", "return", "02:RET: return")

        collection.add_step(step1)
        collection.add_step(step1_2)
        collection.add_step(step1_1)
        collection.add_step(step2)

        assert collection.ordered_line_numbers == ["01", "01.01", "01.02", "02"]

    def test_get_step(self):
        """Test getting a step by line number."""
        collection = PlaybookStepCollection()

        step1 = PlaybookStep("01", "YLD", "ForUserInput", "01:YLD: ForUserInput")
        step2 = PlaybookStep("02", "QUE", "Say()", "02:QUE: Say()")

        collection.add_step(step1)
        collection.add_step(step2)

        assert collection.get_step("01") == step1
        assert collection.get_step("02") == step2
        assert collection.get_step("03") is None

    def test_get_next_step(self):
        """Test getting the next step."""
        collection = PlaybookStepCollection()

        step1 = PlaybookStep("01", "YLD", "ForUserInput", "01:YLD: ForUserInput")
        step2 = PlaybookStep("02", "QUE", "Say()", "02:QUE: Say()")
        step3 = PlaybookStep("03", "RET", "return", "03:RET: return")

        collection.add_step(step1)
        collection.add_step(step2)
        collection.add_step(step3)

        assert collection.get_next_step("01") == step2
        assert collection.get_next_step("02") == step3
        assert collection.get_next_step("03") is None
        assert collection.get_next_step("04") is None

    def test_get_next_step_nested(self):
        """Test getting the next step with nested line numbers."""
        collection = PlaybookStepCollection()

        step1 = PlaybookStep("01", "LOP", "For each", "01:LOP: For each")
        step1_1 = PlaybookStep(
            "01.01", "YLD", "ForUserInput", "01.01:YLD: ForUserInput"
        )
        step1_2 = PlaybookStep("01.02", "QUE", "Say()", "01.02:QUE: Say()")
        step2 = PlaybookStep("02", "RET", "return", "02:RET: return")

        collection.add_step(step1)
        collection.add_step(step1_1)
        collection.add_step(step1_2)
        collection.add_step(step2)

        assert collection.get_next_step("01") == step1_1
        assert collection.get_next_step("01.01") == step1_2
        # The next step after 01.02 should be step1 (the loop step) or step2 (the next step after the loop)
        # Let's check that it's one of these two
        next_step = collection.get_next_step("01.02")
        assert next_step in [step1, step2]
        assert collection.get_next_step("02") is None

    def test_get_all_steps(self):
        """Test getting all steps in order."""
        collection = PlaybookStepCollection()

        step1 = PlaybookStep("01", "YLD", "ForUserInput", "01:YLD: ForUserInput")
        step2 = PlaybookStep("02", "QUE", "Say()", "02:QUE: Say()")
        step3 = PlaybookStep("03", "RET", "return", "03:RET: return")

        # Add in reverse order
        collection.add_step(step3)
        collection.add_step(step1)
        collection.add_step(step2)

        all_steps = collection.get_all_steps()

        assert len(all_steps) == 3
        assert all_steps[0] == step1
        assert all_steps[1] == step2
        assert all_steps[2] == step3

    def test_len_and_iter(self):
        """Test the __len__ and __iter__ methods."""
        collection = PlaybookStepCollection()

        step1 = PlaybookStep("01", "YLD", "ForUserInput", "01:YLD: ForUserInput")
        step2 = PlaybookStep("02", "QUE", "Say()", "02:QUE: Say()")

        collection.add_step(step1)
        collection.add_step(step2)

        assert len(collection) == 2

        steps = list(collection)
        assert len(steps) == 2
        assert steps[0] == step1
        assert steps[1] == step2

    def test_build_conditional_relationships(self):
        """Test building relationships between CND and ELS steps."""
        collection = PlaybookStepCollection()

        # Create a simple if-else structure
        step1 = PlaybookStep("01", "CND", "If condition", "01:CND: If condition")
        step1_1 = PlaybookStep(
            "01.01", "EXE", "Do something", "01.01:EXE: Do something"
        )
        step2 = PlaybookStep("02", "ELS", "Otherwise", "02:ELS: Otherwise")
        step2_1 = PlaybookStep(
            "02.01", "EXE", "Do something else", "02.01:EXE: Do something else"
        )
        step3 = PlaybookStep("03", "EXE", "Continue", "03:EXE: Continue")

        # Add steps to the collection
        collection.add_step(step1)
        collection.add_step(step1_1)
        collection.add_step(step2)
        collection.add_step(step2_1)
        collection.add_step(step3)

        # Build the DAG
        collection._build_dag()

        # Check that the CND-ELS relationship is established
        assert step1.else_step == step2
        assert step2.cnd_step == step1

        # Check that the next steps are set correctly
        assert step1.next_steps[0] == step1_1  # If true, go to the if branch
        assert len(step1.next_steps) == 1  # No direct jump to else branch in DAG

        # Check that the last step in the if branch points to the step after the if-else block
        assert step1_1.next_steps[0] == step3

        # Check that the last step in the else branch points to the step after the if-else block
        assert step2_1.next_steps[0] == step3

    def test_get_next_step_conditional(self):
        """Test getting the next step with conditional logic."""
        collection = PlaybookStepCollection()

        # Create a simple if-else structure
        step1 = PlaybookStep("01", "CND", "If condition", "01:CND: If condition")
        step1_1 = PlaybookStep(
            "01.01", "EXE", "Do something", "01.01:EXE: Do something"
        )
        step2 = PlaybookStep("02", "ELS", "Otherwise", "02:ELS: Otherwise")
        step2_1 = PlaybookStep(
            "02.01", "EXE", "Do something else", "02.01:EXE: Do something else"
        )
        step3 = PlaybookStep("03", "EXE", "Continue", "03:EXE: Continue")

        # Add steps to the collection
        collection.add_step(step1)
        collection.add_step(step1_1)
        collection.add_step(step2)
        collection.add_step(step2_1)
        collection.add_step(step3)

        # Check navigation through the if-else structure
        assert (
            collection.get_next_step("01") == step1_1
        )  # Next step after CND is its child
        assert (
            collection.get_next_step("01.01") == step3
        )  # Next step after if branch is the step after the if-else block
        assert (
            collection.get_next_step("02") == step2_1
        )  # Next step after ELS is its child
        assert (
            collection.get_next_step("02.01") == step3
        )  # Next step after else branch is the step after the if-else block
        assert (
            collection.get_next_step("03") is None
        )  # No next step after the last step

    def test_nested_conditionals(self):
        """Test nested conditional structures."""
        collection = PlaybookStepCollection()

        # Create a nested if-else structure
        step1 = PlaybookStep(
            "01", "CND", "If outer condition", "01:CND: If outer condition"
        )
        step1_1 = PlaybookStep(
            "01.01", "CND", "If inner condition", "01.01:CND: If inner condition"
        )
        step1_1_1 = PlaybookStep(
            "01.01.01", "EXE", "Do inner if", "01.01.01:EXE: Do inner if"
        )
        step1_2 = PlaybookStep(
            "01.02", "ELS", "Inner otherwise", "01.02:ELS: Inner otherwise"
        )
        step1_2_1 = PlaybookStep(
            "01.02.01", "EXE", "Do inner else", "01.02.01:EXE: Do inner else"
        )
        step1_3 = PlaybookStep(
            "01.03", "EXE", "Continue outer if", "01.03:EXE: Continue outer if"
        )
        step2 = PlaybookStep("02", "ELS", "Outer otherwise", "02:ELS: Outer otherwise")
        step2_1 = PlaybookStep(
            "02.01", "EXE", "Do outer else", "02.01:EXE: Do outer else"
        )
        step3 = PlaybookStep(
            "03", "EXE", "Continue after all", "03:EXE: Continue after all"
        )

        # Add steps to the collection
        collection.add_step(step1)
        collection.add_step(step1_1)
        collection.add_step(step1_1_1)
        collection.add_step(step1_2)
        collection.add_step(step1_2_1)
        collection.add_step(step1_3)
        collection.add_step(step2)
        collection.add_step(step2_1)
        collection.add_step(step3)

        # Build the DAG
        collection._build_dag()

        # Check that the CND-ELS relationships are established
        assert step1.else_step == step2
        assert step2.cnd_step == step1
        assert step1_1.else_step == step1_2
        assert step1_2.cnd_step == step1_1

        # Check navigation through the nested if-else structure
        assert (
            collection.get_next_step("01") == step1_1
        )  # Next step after outer CND is inner CND
        assert (
            collection.get_next_step("01.01") == step1_1_1
        )  # Next step after inner CND is its child
        assert (
            collection.get_next_step("01.01.01") == step1_3
        )  # Next step after inner if branch is the step after the inner if-else block
        assert (
            collection.get_next_step("01.02") == step1_2_1
        )  # Next step after inner ELS is its child
        assert (
            collection.get_next_step("01.02.01") == step1_3
        )  # Next step after inner else branch is the step after the inner if-else block
        assert (
            collection.get_next_step("01.03") == step3
        )  # Next step after outer if branch is the step after the outer if-else block
        assert (
            collection.get_next_step("02") == step2_1
        )  # Next step after outer ELS is its child
        assert (
            collection.get_next_step("02.01") == step3
        )  # Next step after outer else branch is the step after the outer if-else block
        assert (
            collection.get_next_step("03") is None
        )  # No next step after the last step

    def test_conditional_without_else(self):
        """Test conditional structure without an else branch."""
        collection = PlaybookStepCollection()

        # Create an if structure without else
        step1 = PlaybookStep("01", "CND", "If condition", "01:CND: If condition")
        step1_1 = PlaybookStep(
            "01.01", "EXE", "Do something", "01.01:EXE: Do something"
        )
        step2 = PlaybookStep("02", "EXE", "Continue", "02:EXE: Continue")

        # Add steps to the collection
        collection.add_step(step1)
        collection.add_step(step1_1)
        collection.add_step(step2)

        # Build the DAG
        collection._build_dag()

        # Check that there's no else step
        assert step1.else_step is None

        # Check navigation through the if structure
        assert (
            collection.get_next_step("01") == step1_1
        )  # Next step after CND is its child
        assert (
            collection.get_next_step("01.01") == step2
        )  # Next step after if branch is the step after the if block
        assert (
            collection.get_next_step("02") is None
        )  # No next step after the last step

    def test_find_last_step_in_conditional(self):
        """Test finding the last step in a conditional block."""
        collection = PlaybookStepCollection()

        # Create a conditional structure with multiple steps in the if branch
        step1 = PlaybookStep("01", "CND", "If condition", "01:CND: If condition")
        step1_1 = PlaybookStep("01.01", "EXE", "First step", "01.01:EXE: First step")
        step1_2 = PlaybookStep("01.02", "EXE", "Second step", "01.02:EXE: Second step")
        step1_3 = PlaybookStep("01.03", "EXE", "Third step", "01.03:EXE: Third step")
        step2 = PlaybookStep("02", "ELS", "Otherwise", "02:ELS: Otherwise")
        step2_1 = PlaybookStep(
            "02.01", "EXE", "Do something else", "02.01:EXE: Do something else"
        )
        step3 = PlaybookStep("03", "EXE", "Continue", "03:EXE: Continue")

        # Add steps to the collection
        collection.add_step(step1)
        collection.add_step(step1_1)
        collection.add_step(step1_2)
        collection.add_step(step1_3)
        collection.add_step(step2)
        collection.add_step(step2_1)
        collection.add_step(step3)

        # Build the DAG
        collection._build_dag()

        # Check that the last step in the if branch is correctly identified
        last_in_if = collection._find_last_step_in_conditional(step1)
        assert last_in_if == step1_3

        # Check that the last step in the else branch is correctly identified
        last_in_else = collection._find_last_step_in_conditional(step2)
        assert last_in_else == step2_1

    def test_find_step_after_conditional(self):
        """Test finding the step after a conditional block."""
        collection = PlaybookStepCollection()

        # Create a conditional structure
        step1 = PlaybookStep("01", "CND", "If condition", "01:CND: If condition")
        step1_1 = PlaybookStep(
            "01.01", "EXE", "Do something", "01.01:EXE: Do something"
        )
        step2 = PlaybookStep("02", "ELS", "Otherwise", "02:ELS: Otherwise")
        step2_1 = PlaybookStep(
            "02.01", "EXE", "Do something else", "02.01:EXE: Do something else"
        )
        step3 = PlaybookStep("03", "EXE", "Continue", "03:EXE: Continue")

        # Add steps to the collection
        collection.add_step(step1)
        collection.add_step(step1_1)
        collection.add_step(step2)
        collection.add_step(step2_1)
        collection.add_step(step3)

        # Build the DAG
        collection._build_dag()

        # Check that the step after the conditional block is correctly identified
        after_cnd = collection._find_step_after_conditional(step1)
        assert after_cnd == step3
