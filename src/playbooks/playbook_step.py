"""Playbook step module for representing steps in a playbook."""

import re
from typing import Dict, Iterator, List, Optional


class PlaybookStep:
    """Represents a step in a playbook."""

    def __init__(
        self,
        line_number: str,
        step_type: str,
        content: str,
        raw_text: str,
        source_line_number: Optional[int] = None,
        source_file_path: Optional[str] = None,
    ):
        """Initialize a playbook step.

        Args:
            line_number: The line number of the step (e.g., "01", "01.01").
            step_type: The type of the step (e.g., "YLD", "RET", "QUE", "LOP", "CND", "ELS").
            content: The content of the step after the step type.
            raw_text: The raw text of the step as it appears in the playbook.
            source_line_number: The line number in the source markdown where this
                step is defined.
            source_file_path: The file path of the source markdown where this
                step is defined.
        """
        self.line_number = line_number
        self.step_type = step_type
        self.content = content
        self.raw_text = raw_text
        self.source_line_number = source_line_number
        self.source_file_path = source_file_path

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

        # Match line numbers like "02", "02.01" followed by a step type like "YLD", "EXE"
        pattern = r"^(\d+(?:\.\d+)*):([A-Z]+)(.*)$"
        match = re.match(pattern, text.strip())

        if not match:
            return None

        try:
            line_number = match.group(1)
            step_type = match.group(2)
            content = match.group(3) or ""
            content = content.strip()

            # Remove leading colon if present
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

    def __str__(self) -> str:
        """Return a string representation of the step."""
        return f"{self.line_number}:{self.step_type}: {self.content}"

    def __repr__(self) -> str:
        """Return a string representation of the step."""
        return f"PlaybookStep({self.line_number}, {self.step_type}, {self.content})"

    def execute(self) -> None:
        """Execute this step (placeholder for future implementation)."""
        pass


class PlaybookStepCollection:
    """A collection of playbook steps."""

    def __init__(self) -> None:
        """Initialize a playbook step collection."""
        self.steps: Dict[str, PlaybookStep] = {}
        self.ordered_line_numbers: List[str] = []
        self.entry_point: Optional[PlaybookStep] = None
        self._dag_built = False

    def add_step(self, step: PlaybookStep) -> None:
        """Add a step to the collection.

        Args:
            step: The step to add.
        """
        self.steps[step.line_number] = step

        # Add to ordered list if not already present
        if step.line_number not in self.ordered_line_numbers:
            self._insert_ordered(step.line_number)

        # Mark that DAG needs rebuilding
        self._dag_built = False

    def _insert_ordered(self, line_number: str) -> None:
        """Insert a line number into the ordered list at the correct position.

        Args:
            line_number: The line number to insert.
        """
        if not self.ordered_line_numbers:
            self.ordered_line_numbers.append(line_number)
            return

        # Insert at the correct position based on line number comparison
        for i, existing in enumerate(self.ordered_line_numbers):
            if self._compare_line_numbers(line_number, existing) < 0:
                self.ordered_line_numbers.insert(i, line_number)
                return

        # If we get here, add to the end
        self.ordered_line_numbers.append(line_number)

    def _compare_line_numbers(self, a: str, b: str) -> int:
        """Compare two line numbers lexicographically.

        Args:
            a: First line number.
            b: Second line number.

        Returns:
            -1 if a < b, 0 if a == b, 1 if a > b.
        """
        a_parts = [int(p) for p in a.split(".")]
        b_parts = [int(p) for p in b.split(".")]

        # Compare parts until we find a difference
        for a_part, b_part in zip(a_parts, b_parts):
            if a_part != b_part:
                return -1 if a_part < b_part else 1

        # If one is a prefix of the other, the shorter one comes first
        return len(a_parts) - len(b_parts)

    def _get_next_line_number_at_same_level(self, line_number: str) -> str:
        """Get the next line number at the same hierarchical level.

        Args:
            line_number: The current line number.

        Returns:
            The next line number at the same level.
        """
        if "." in line_number:
            parent_line, sub_line = line_number.rsplit(".", 1)
            return f"{parent_line}.{int(sub_line) + 1:02d}"
        return f"{int(line_number) + 1:02d}"

    def _build_dag(self) -> None:
        """Build the directed acyclic graph (DAG) for step navigation.

        Establishes relationships between steps:
        - Parent-child relationships for nested steps
        - Sequential step relationships
        - Loop and conditional relationships
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

        # Set entry point
        if self.ordered_line_numbers:
            self.entry_point = self.steps[self.ordered_line_numbers[0]]

        # Build parent-child relationships
        self._build_parent_child_relationships()

        # Mark loop steps
        self._mark_loop_steps()

        # Build sequential relationships
        self._build_sequential_relationships()

        # Special handling for loops
        self._build_loop_relationships()

        # Build conditional relationships
        self._build_conditional_relationships()

        self._dag_built = True

    def _build_parent_child_relationships(self) -> None:
        """Build parent-child relationships between steps."""
        for step in self.steps.values():
            parent_line = step.get_parent_line_number()
            if parent_line and parent_line in self.steps:
                parent_step = self.steps[parent_line]
                step.parent_step = parent_step
                parent_step.child_steps.append(step)

    def _mark_loop_steps(self) -> None:
        """Identify and mark steps that are part of a loop."""
        for step in self.steps.values():
            if step.is_loop():
                for child_step in step.child_steps:
                    child_step.is_in_loop = True
                    child_step.loop_entry = step
                    self._mark_descendants_in_loop(child_step, step)

    def _build_sequential_relationships(self) -> None:
        """Build sequential relationships between steps."""
        for i, line_number in enumerate(self.ordered_line_numbers[:-1]):
            step = self.steps[line_number]
            next_line = self.ordered_line_numbers[i + 1]
            next_step = self.steps[next_line]
            step.next_steps.append(next_step)

    def _build_loop_relationships(self) -> None:
        """Build relationships for loop steps."""
        for step in self.steps.values():
            if step.is_loop():
                child_steps = sorted(step.child_steps, key=lambda s: s.line_number)
                if not child_steps:
                    continue

                # Loop step's next step is its first child
                step.next_steps = [child_steps[0]]

                # Last step in loop goes back to loop entry
                last_in_loop = self._find_last_step_in_loop(step)
                if last_in_loop:
                    last_in_loop.next_steps = [step]

                    # Add exit path from loop
                    after_loop = self._find_step_after_loop(step)
                    if after_loop:
                        step.next_steps.append(after_loop)

    def _build_conditional_relationships(self) -> None:
        """Build relationships between conditional (CND) and else (ELS) steps."""
        cnd_steps = [step for step in self.steps.values() if step.is_conditional()]

        for cnd_step in cnd_steps:
            next_line = self._get_next_line_number_at_same_level(cnd_step.line_number)

            # Check if next step is an ELSE
            if next_line in self.steps and self.steps[next_line].is_else():
                els_step = self.steps[next_line]
                cnd_step.else_step = els_step
                els_step.cnd_step = cnd_step

                # Make if branch exit point connect to else branch exit point
                last_in_if = self._find_last_step_in_conditional(cnd_step)
                last_in_else = self._find_last_step_in_conditional(els_step)
                if last_in_if and last_in_else and last_in_else.next_steps:
                    last_in_if.next_steps = last_in_else.next_steps

    def _mark_descendants_in_loop(
        self, step: PlaybookStep, loop_step: PlaybookStep
    ) -> None:
        """Recursively mark all descendant steps as being in a loop.

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
        loop_steps = [
            step for step in self.steps.values() if step.loop_entry == loop_step
        ]

        if not loop_steps:
            return None

        return sorted(loop_steps, key=lambda s: s.line_number)[-1]

    def _find_step_after_loop(self, loop_step: PlaybookStep) -> Optional[PlaybookStep]:
        """Find the step that comes after a loop.

        Args:
            loop_step: The loop step

        Returns:
            The step after the loop or None if not found
        """
        if loop_step.line_number not in self.ordered_line_numbers:
            return None

        loop_index = self.ordered_line_numbers.index(loop_step.line_number)
        loop_level = len(loop_step.line_number.split("."))

        # Find first step after loop that is not in this loop and at same/higher level
        for i in range(loop_index + 1, len(self.ordered_line_numbers)):
            next_line = self.ordered_line_numbers[i]
            next_step = self.steps[next_line]

            # Skip if step is in this loop
            if next_step.is_in_loop and next_step.loop_entry == loop_step:
                continue

            # Check if at same or higher level in hierarchy
            next_level = len(next_step.line_number.split("."))
            if next_level <= loop_level:
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
        # Find all direct children and nested descendants
        block_steps = []

        # Direct children
        block_steps.extend(cnd_or_els_step.child_steps)

        # Nested descendants
        for child in cnd_or_els_step.child_steps:
            for step in self.steps.values():
                if (
                    step.get_parent_line_number()
                    and step.get_parent_line_number().startswith(child.line_number)
                ):
                    block_steps.append(step)

        if not block_steps:
            return None

        return sorted(block_steps, key=lambda s: s.line_number)[-1]

    def _find_step_after_conditional(
        self, cnd_step: PlaybookStep
    ) -> Optional[PlaybookStep]:
        """Find the step after a conditional block (including its else branch if any).

        Args:
            cnd_step: The conditional step

        Returns:
            The step after the conditional block or None if not found
        """
        # Case 1: If there's an else step
        if cnd_step.else_step:
            last_in_else = self._find_last_step_in_conditional(cnd_step.else_step)
            if last_in_else:
                next_line = self._get_next_line_number_at_same_level(
                    cnd_step.else_step.line_number
                )
                return self.steps.get(next_line)
        # Case 2: No else step
        else:
            next_line = self._get_next_line_number_at_same_level(cnd_step.line_number)

            # If next step is an else for this conditional, skip it
            if (
                next_line in self.steps
                and self.steps[next_line].is_else()
                and self.steps[next_line].cnd_step == cnd_step
            ):
                next_line = self._get_next_line_number_at_same_level(next_line)

            return self.steps.get(next_line)

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
        """Get the next step after the given line number based on the DAG.

        Args:
            line_number: The line number to start from.

        Returns:
            The next step or None if there is no next step.
        """
        # Build the DAG if needed
        if not self._dag_built:
            self._build_dag()

        current_step = self.steps.get(line_number)
        if not current_step:
            return None

        # If the step has explicit next steps from the DAG, use that
        if current_step.next_steps:
            return current_step.next_steps[0]

        # Special case: at end of loop, return to loop start
        if current_step.is_in_loop and current_step.loop_entry:
            loop_entry = current_step.loop_entry
            first_child = (
                sorted(loop_entry.child_steps, key=lambda s: s.line_number)[0]
                if loop_entry.child_steps
                else None
            )
            if first_child:
                return first_child

        # Special case: at end of conditional branch
        if current_step.parent_step:
            # Handle conditional and else branch endings
            if current_step.parent_step.is_conditional():
                after_cnd = self._find_step_after_conditional(current_step.parent_step)
                if after_cnd:
                    return after_cnd
            elif (
                current_step.parent_step.is_else() and current_step.parent_step.cnd_step
            ):
                after_cnd = self._find_step_after_conditional(
                    current_step.parent_step.cnd_step
                )
                if after_cnd:
                    return after_cnd

        # Fall back to sequential navigation
        if line_number in self.ordered_line_numbers:
            current_index = self.ordered_line_numbers.index(line_number)
            if current_index + 1 < len(self.ordered_line_numbers):
                next_line = self.ordered_line_numbers[current_index + 1]
                return self.steps[next_line]

        return None

    def get_all_steps(self) -> List[PlaybookStep]:
        """Get all steps in order.

        Returns:
            A list of all steps in order.
        """
        return [self.steps[line] for line in self.ordered_line_numbers]

    def __len__(self) -> int:
        """Return the number of steps in the collection."""
        return len(self.steps)

    def __iter__(self) -> Iterator[PlaybookStep]:
        """Iterate over the steps in order."""
        for line in self.ordered_line_numbers:
            yield self.steps[line]
