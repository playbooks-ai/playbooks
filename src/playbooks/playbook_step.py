"""Playbook step module for representing steps in a playbook."""

import re
from typing import Dict, List, Optional


class PlaybookStep:
    """Represents a step in a playbook."""

    def __init__(
        self,
        line_number: str,
        step_type: str,
        content: str,
        raw_text: str,
    ):
        """Initialize a playbook step.

        Args:
            line_number: The line number of the step (e.g., "01", "01.01").
            step_type: The type of the step (e.g., "YLD", "RET", "QUE").
            content: The content of the step after the step type.
            raw_text: The raw text of the step as it appears in the playbook.
        """
        self.line_number = line_number
        self.step_type = step_type
        self.content = content
        self.raw_text = raw_text

        # DAG navigation properties
        self.next_steps: List[PlaybookStep] = []
        self.parent_step: Optional[PlaybookStep] = None
        self.child_steps: List[PlaybookStep] = []
        self.is_in_loop = False
        self.loop_entry: Optional[PlaybookStep] = None
        self.else_step: Optional[PlaybookStep] = None
        self.cnd_step: Optional[PlaybookStep] = None

    @classmethod
    def from_text(cls, text: str) -> Optional["PlaybookStep"]:
        """Create a PlaybookStep from a text line.

        Args:
            text: The text line to parse.

        Returns:
            A PlaybookStep instance or None if the text is not a valid step.
        """
        if not text:
            return None

        # Regex pattern to match line numbers like "02", "02.01", "03.02.89" followed by a colon
        # and then a step type like "YLD", "EXE", "RET"
        pattern = r"^(\d+(?:\.\d+)*):([A-Z]+)(.*)$"
        match = re.match(pattern, text.strip())

        if not match:
            return None

        try:
            line_number = match.group(1)
            step_type = match.group(2)
            content = match.group(3) or ""
            content = content.strip()

            # Remove leading colon and space if present
            if content.startswith(":"):
                content = content[1:].strip()

            return cls(
                line_number=line_number,
                step_type=step_type,
                content=content,
                raw_text=text,
            )
        except Exception:
            return None

    def is_yield(self) -> bool:
        """Check if this step is a yield step."""
        return self.step_type == "YLD"

    def is_return(self) -> bool:
        """Check if this step is a return step."""
        return self.step_type == "RET"

    def is_loop(self) -> bool:
        """Check if this step is a loop step."""
        return self.step_type == "LOP"

    def is_conditional(self) -> bool:
        """Check if this step is a conditional step."""
        return self.step_type == "CND"

    def is_else(self) -> bool:
        """Check if this step is an else step."""
        return self.step_type == "ELS"

    def get_parent_line_number(self) -> Optional[str]:
        """Get the parent line number for a nested line.

        For example, for "01.02", the parent is "01".

        Returns:
            The parent line number or None if this is a top-level line.
        """
        if "." in self.line_number:
            return self.line_number.rsplit(".", 1)[0]
        return None

    def get_next_line_number(self) -> Optional[str]:
        """Calculate the next line number after this step.

        Returns:
            The next line number or None if it can't be calculated.
        """
        try:
            if "." in self.line_number:
                # For nested line numbers like "01.01"
                parent_line, sub_line = self.line_number.rsplit(".", 1)
                next_sub_line = f"{int(sub_line) + 1:02d}"
                return f"{parent_line}.{next_sub_line}"
            else:
                # For simple line numbers like "01"
                return f"{int(self.line_number) + 1:02d}"
        except Exception:
            return None

    def __str__(self) -> str:
        """Return a string representation of the step."""
        return f"{self.line_number}:{self.step_type}: {self.content}"

    def __repr__(self) -> str:
        """Return a string representation of the step."""
        return f"PlaybookStep({self.line_number}, {self.step_type}, {self.content})"


class PlaybookStepCollection:
    """A collection of playbook steps."""

    def __init__(self):
        """Initialize a playbook step collection."""
        self.steps: Dict[str, PlaybookStep] = {}
        self.ordered_line_numbers: list[str] = []
        self.entry_point: Optional[PlaybookStep] = None
        self._dag_built = False

    def add_step(self, step: PlaybookStep) -> None:
        """Add a step to the collection.

        Args:
            step: The step to add.
        """
        self.steps[step.line_number] = step

        # Maintain the ordered list of line numbers
        if step.line_number not in self.ordered_line_numbers:
            # Insert in the correct position to maintain order
            self._insert_ordered(step.line_number)

        # Mark that we need to rebuild the DAG
        self._dag_built = False

    def _insert_ordered(self, line_number: str) -> None:
        """Insert a line number in the ordered list.

        Args:
            line_number: The line number to insert.
        """
        # Simple insertion sort
        if not self.ordered_line_numbers:
            self.ordered_line_numbers.append(line_number)
            return

        # Handle nested line numbers
        for i, existing in enumerate(self.ordered_line_numbers):
            if self._compare_line_numbers(line_number, existing) < 0:
                self.ordered_line_numbers.insert(i, line_number)
                return

        # If we get here, add to the end
        self.ordered_line_numbers.append(line_number)

    def _compare_line_numbers(self, a: str, b: str) -> int:
        """Compare two line numbers.

        Args:
            a: First line number.
            b: Second line number.

        Returns:
            -1 if a < b, 0 if a == b, 1 if a > b.
        """
        # Split into parts (for nested line numbers)
        a_parts = a.split(".")
        b_parts = b.split(".")

        # Compare main line numbers
        a_main = int(a_parts[0])
        b_main = int(b_parts[0])

        if a_main != b_main:
            return -1 if a_main < b_main else 1

        # If main line numbers are equal, compare sub-line numbers if they exist
        if len(a_parts) > 1 and len(b_parts) > 1:
            a_sub = int(a_parts[1])
            b_sub = int(b_parts[1])
            return -1 if a_sub < b_sub else (0 if a_sub == b_sub else 1)

        # If one has a sub-line and the other doesn't, the one without comes first
        if len(a_parts) > 1:
            return 1
        if len(b_parts) > 1:
            return -1

        # They're equal
        return 0

    def _get_next_line_number_at_same_level(self, line_number: str) -> str:
        """Get the next line number at the same level.

        For example, for "01", the next line is "02".
        For "01.01", the next line is "01.02".

        Args:
            line_number: The current line number.

        Returns:
            The next line number at the same level.
        """
        if "." in line_number:
            # For nested line numbers like "01.01"
            parent_line, sub_line = line_number.rsplit(".", 1)
            return f"{parent_line}.{int(sub_line) + 1:02d}"
        else:
            # For simple line numbers like "01"
            return f"{int(line_number) + 1:02d}"

    def _build_dag(self) -> None:
        """Build the directed acyclic graph (DAG) for navigation.

        This method establishes the relationships between steps:
        - Parent-child relationships for nested steps
        - Next step relationships for sequential execution
        - Loop relationships for loop navigation
        - Conditional (CND) and else (ELS) relationships
        """
        if self._dag_built or not self.steps:
            return

        # Reset all navigation properties
        for step in self.steps.values():
            step.next_steps = []
            step.parent_step = None
            step.child_steps = []
            step.is_in_loop = False
            step.loop_entry = None
            step.else_step = None
            step.cnd_step = None

        # Set the entry point to the first step
        if self.ordered_line_numbers:
            self.entry_point = self.steps[self.ordered_line_numbers[0]]

        # Build parent-child relationships
        for _, step in self.steps.items():
            parent_line = step.get_parent_line_number()
            if parent_line and parent_line in self.steps:
                parent_step = self.steps[parent_line]
                step.parent_step = parent_step
                parent_step.child_steps.append(step)

        # Identify loops and mark steps in loops
        for _, step in self.steps.items():
            if step.is_loop():
                # Mark all child steps as being in this loop
                for child_step in step.child_steps:
                    child_step.is_in_loop = True
                    child_step.loop_entry = step

                    # Recursively mark all descendants
                    self._mark_descendants_in_loop(child_step, step)

        # Build next step relationships
        for i, line_number in enumerate(self.ordered_line_numbers):
            step = self.steps[line_number]

            # If this is the last step, it has no next step
            if i == len(self.ordered_line_numbers) - 1:
                continue

            # Get the next step in the ordered list
            next_line = self.ordered_line_numbers[i + 1]
            next_step = self.steps[next_line]

            # Add the next step to this step's next_steps list
            step.next_steps.append(next_step)

        # Special handling for loops
        for _, step in self.steps.items():
            if step.is_loop():
                # Find the first child step (loop entry)
                child_steps = sorted(step.child_steps, key=lambda s: s.line_number)
                if child_steps:
                    # The loop step's next step is its first child
                    step.next_steps = [child_steps[0]]

                    # Find the last step in the loop
                    last_in_loop = self._find_last_step_in_loop(step)
                    if last_in_loop:
                        # The last step in the loop goes back to the loop entry
                        last_in_loop.next_steps = [step]

                        # Find the step after the loop
                        after_loop = self._find_step_after_loop(step)
                        if after_loop:
                            # The loop step also points to the step after the loop
                            # (this will be used when the loop condition is false)
                            step.next_steps.append(after_loop)

        # Identify CND-ELS relationships
        self._build_conditional_relationships()

        self._dag_built = True

    def _build_conditional_relationships(self) -> None:
        """Build relationships between CND and ELS steps."""
        # Find all CND steps
        cnd_steps = [step for step in self.steps.values() if step.is_conditional()]

        # For each CND step, find its corresponding ELS step (if any)
        for cnd_step in cnd_steps:
            # Get the next line number at the same level
            next_line = self._get_next_line_number_at_same_level(cnd_step.line_number)

            # Check if the next line is an ELS step
            if next_line in self.steps and self.steps[next_line].is_else():
                els_step = self.steps[next_line]
                cnd_step.else_step = els_step
                els_step.cnd_step = cnd_step

                # Update the next step of the last step in the if branch
                last_in_if = self._find_last_step_in_conditional(cnd_step)
                if last_in_if:
                    last_in_else = self._find_last_step_in_conditional(els_step)
                    last_in_if.next_steps = last_in_else.next_steps

    def _mark_descendants_in_loop(
        self, step: PlaybookStep, loop_step: PlaybookStep
    ) -> None:
        """Recursively mark all descendants of a step as being in a loop.

        Args:
            step: The step whose descendants should be marked
            loop_step: The loop step that contains these steps
        """
        for child in step.child_steps:
            child.is_in_loop = True
            child.loop_entry = loop_step
            self._mark_descendants_in_loop(child, loop_step)

    def _find_last_step_in_loop(
        self, loop_step: PlaybookStep
    ) -> Optional[PlaybookStep]:
        """Find the last step in a loop.

        Args:
            loop_step: The loop step

        Returns:
            The last step in the loop or None if not found
        """
        # Get all steps in the loop
        loop_steps = []
        for _, step in self.steps.items():
            if step.loop_entry == loop_step:
                loop_steps.append(step)

        if not loop_steps:
            return None

        # Sort by line number and return the last one
        return sorted(loop_steps, key=lambda s: s.line_number)[-1]

    def _find_step_after_loop(self, loop_step: PlaybookStep) -> Optional[PlaybookStep]:
        """Find the step that comes after a loop.

        Args:
            loop_step: The loop step

        Returns:
            The step after the loop or None if not found
        """
        # Find the loop step's index in the ordered list
        if loop_step.line_number not in self.ordered_line_numbers:
            return None

        loop_index = self.ordered_line_numbers.index(loop_step.line_number)

        # Find the first step after the loop that is not in the loop
        for i in range(loop_index + 1, len(self.ordered_line_numbers)):
            next_line = self.ordered_line_numbers[i]
            next_step = self.steps[next_line]

            # If this step is not in the loop or any nested loop within this loop
            if not next_step.is_in_loop or next_step.loop_entry != loop_step:
                # Check if this step is at the same level as the loop or higher
                if "." not in next_step.line_number or len(
                    next_step.line_number.split(".")
                ) <= len(loop_step.line_number.split(".")):
                    return next_step

        return None

    def _find_last_step_in_conditional(
        self, cnd_or_els_step: PlaybookStep
    ) -> Optional[PlaybookStep]:
        """Find the last step in a conditional or else block.

        Args:
            cnd_or_els_step: The conditional or else step

        Returns:
            The last step in the conditional/else block or None if not found
        """
        # Get all steps in the conditional/else block
        block_steps = []
        for _, step in self.steps.items():
            if step.parent_step == cnd_or_els_step:
                block_steps.append(step)

                # Also include any nested steps
                for nested_step in self.steps.values():
                    if (
                        nested_step.get_parent_line_number()
                        and nested_step.get_parent_line_number().startswith(
                            step.line_number
                        )
                    ):
                        block_steps.append(nested_step)

        if not block_steps:
            return None

        # Sort by line number and return the last one
        return sorted(block_steps, key=lambda s: s.line_number)[-1]

    def _find_step_after_conditional(
        self, cnd_step: PlaybookStep
    ) -> Optional[PlaybookStep]:
        """Find the step that comes after a conditional block (including its else branch if any).

        Args:
            cnd_step: The conditional step

        Returns:
            The step after the conditional block or None if not found
        """
        # If there's an else step, find the step after the else block
        if cnd_step.else_step:
            # Find the last step in the else block
            last_in_else = self._find_last_step_in_conditional(cnd_step.else_step)
            if last_in_else:
                # Get the next line number at the same level as the else step
                next_line = self._get_next_line_number_at_same_level(
                    cnd_step.else_step.line_number
                )

                # Check if the next line exists
                if next_line in self.steps:
                    return self.steps[next_line]
        else:
            # Find the last step in the conditional block
            last_in_cnd = self._find_last_step_in_conditional(cnd_step)
            if last_in_cnd:
                # Get the next line number at the same level as the conditional step
                next_line = self._get_next_line_number_at_same_level(
                    cnd_step.line_number
                )

                # Check if the next line exists
                if next_line in self.steps:
                    # Skip the else step if there is one
                    if (
                        self.steps[next_line].is_else()
                        and self.steps[next_line].cnd_step == cnd_step
                    ):
                        # Get the next line after the else step
                        next_after_else = self._get_next_line_number_at_same_level(
                            next_line
                        )

                        if next_after_else in self.steps:
                            return self.steps[next_after_else]
                    else:
                        return self.steps[next_line]

        return None

    def get_step(self, line_number: str) -> Optional[PlaybookStep]:
        """Get a step by line number.

        Args:
            line_number: The line number of the step.

        Returns:
            The step or None if not found.
        """
        return self.steps.get(line_number)

    def get_next_step(self, line_number: str) -> Optional[PlaybookStep]:
        """Get the next step after the given line number.

        Args:
            line_number: The line number to start from.

        Returns:
            The next step or None if there is no next step.
        """
        # Build the DAG if it hasn't been built yet
        if not self._dag_built:
            self._build_dag()

        # Get the current step
        current_step = self.steps.get(line_number)
        if not current_step:
            return None

        # If the step has next steps defined in the DAG, return the first one
        if current_step.next_steps:
            return current_step.next_steps[0]

        # If we're in a loop, check if we should loop back
        if current_step.is_in_loop and current_step.loop_entry:
            # Find the first step in the loop
            loop_entry = current_step.loop_entry
            if loop_entry.child_steps:
                first_in_loop = sorted(
                    loop_entry.child_steps, key=lambda s: s.line_number
                )[0]
                return first_in_loop

        # If we're in a conditional, check if we should go to the else branch
        if current_step.is_conditional() and current_step.else_step:
            # If the condition is false, go to the else branch
            # Note: The actual condition evaluation happens at runtime
            # Here we're just setting up the navigation paths
            return current_step.else_step

        # If we're at the end of a conditional branch, go to the step after the conditional
        if current_step.parent_step and current_step.parent_step.is_conditional():
            # Find the step after the conditional
            after_cnd = self._find_step_after_conditional(current_step.parent_step)
            if after_cnd:
                return after_cnd

        # If we're at the end of an else branch, go to the step after the conditional
        if (
            current_step.parent_step
            and current_step.parent_step.is_else()
            and current_step.parent_step.cnd_step
        ):
            # Find the step after the conditional
            after_cnd = self._find_step_after_conditional(
                current_step.parent_step.cnd_step
            )
            if after_cnd:
                return after_cnd

        # Fall back to the original behavior
        if line_number not in self.ordered_line_numbers:
            return None

        current_index = self.ordered_line_numbers.index(line_number)
        if current_index + 1 >= len(self.ordered_line_numbers):
            return None

        next_line = self.ordered_line_numbers[current_index + 1]
        return self.steps[next_line]

    def get_all_steps(self) -> list[PlaybookStep]:
        """Get all steps in order.

        Returns:
            A list of all steps in order.
        """
        return [self.steps[line] for line in self.ordered_line_numbers]

    def __len__(self) -> int:
        """Return the number of steps in the collection."""
        return len(self.steps)

    def __iter__(self):
        """Iterate over the steps in order."""
        for line in self.ordered_line_numbers:
            yield self.steps[line]
