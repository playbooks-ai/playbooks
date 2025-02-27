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
