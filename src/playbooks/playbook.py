import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from .enums import PlaybookExecutionType
from .playbook_step import PlaybookStep, PlaybookStepCollection


class PlaybookTrigger:
    """Represents a trigger that can start a playbook."""

    def __init__(self, playbook_klass: str, playbook_signature: str, trigger: str):
        """Initialize a PlaybookTrigger.

        Args:
            playbook_klass: The class name of the playbook.
            playbook_signature: The signature of the playbook function.
            list_item: The AST node representing the trigger in the markdown.
        """
        self.playbook_klass = playbook_klass
        self.playbook_signature = playbook_signature
        self.trigger = trigger
        # Example text: "01:BGN When the agent starts running"
        self.trigger_name = self.trigger.split(" ")[0]
        self.trigger_description = " ".join(self.trigger.split(" ")[1:])
        self.is_begin = "BGN" in self.trigger_name

    def __str__(self) -> str:
        """Return a string representation of the trigger."""
        signature = self.playbook_signature.split(" ->")[0]
        return f'- {self.trigger_description}, `Trigger["{self.playbook_klass}:{self.trigger_name}"]` by enqueuing `{signature}`'


class PlaybookTriggers:
    """Collection of triggers for a playbook."""

    def __init__(
        self,
        playbook_klass: str,
        playbook_signature: str,
        triggers: List[str],
    ):
        """Initialize a PlaybookTriggers collection.

        Args:
            playbook_klass: The class name of the playbook.
            playbook_signature: The signature of the playbook function.
            h3: The AST node representing the triggers section.
        """
        self.playbook_klass = playbook_klass
        self.playbook_signature = playbook_signature
        self.triggers = [
            PlaybookTrigger(
                playbook_klass=self.playbook_klass,
                playbook_signature=self.playbook_signature,
                trigger=trigger,
            )
            for trigger in triggers
        ]


class Playbook:
    """Represents a playbook that can be executed by an agent.

    Playbooks can be of two types:
    - MD: Markdown playbooks written in the step format.
    - PYTHON: Python playbooks written in Python code.
    """

    @classmethod
    def from_h2(cls, h2: Dict[str, Any]) -> "Playbook":
        """Create a Playbook from an H2 AST node.

        Args:
            h2: Dictionary representing an H2 AST node

        Returns:
            A new playbook instance

        Raises:
            ValueError: If the H2 structure is invalid or required sections are missing
        """
        cls._validate_h2_structure(h2)
        signature, klass, export = cls.parse_title(h2.get("text", "").strip())

        description, h3s = cls._extract_description_and_h3s(h2)

        # Determine playbook type based on presence of a Code h3 section
        # Markdown playbook (MD)
        return cls._create_md_playbook(h2, klass, signature, description, h3s, export)

    @staticmethod
    def _validate_h2_structure(h2: Dict[str, Any]) -> None:
        """Verify that the H2 node has a valid structure.

        Args:
            h2: The H2 AST node to validate.

        Raises:
            ValueError: If H2 contains nested H1 or H2 nodes.
            AssertionError: If the node is not an H2 node.
        """

        def check_no_nested_headers(node: Dict[str, Any]) -> None:
            for child in node.get("children", []):
                if child.get("type") in ["h1", "h2"]:
                    raise ValueError("H2 is not expected to have H1s or H2s")
                check_no_nested_headers(child)

        assert h2.get("type") == "h2", "Node must be an H2 node"
        check_no_nested_headers(h2)

    @staticmethod
    def _extract_description_and_h3s(
        h2: Dict[str, Any],
    ) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """Extract description and h3 sections from H2 node.

        Args:
            h2: The H2 AST node.

        Returns:
            A tuple containing the description text and a list of H3 nodes.
        """
        description_parts = []
        h3s = []
        for child in h2.get("children", []):
            if child.get("type") == "h3":
                h3s.append(child)
            else:
                description_parts.append(child.get("text", "").strip())

        description = "\n".join(description_parts).strip() or None
        return description, h3s

    @classmethod
    def _create_md_playbook(
        cls,
        h2: Dict[str, Any],
        klass: str,
        signature: str,
        description: Optional[str],
        h3s: List[Dict[str, Any]],
        export: bool,
    ) -> "Playbook":
        """Create a markdown (MD) type playbook.

        Args:
            h2: The H2 AST node.
            klass: The playbook class name.
            signature: The playbook signature.
            description: The playbook description.
            h3s: The list of H3 sections.

        Returns:
            A new MD playbook instance.

        Raises:
            ValueError: If an unknown H3 section is encountered.
        """
        triggers = None
        steps = None
        notes = None
        step_collection = PlaybookStepCollection()

        for h3 in h3s:
            h3_title = h3.get("text", "").strip().lower()
            if h3_title == "triggers":
                triggers = PlaybookTriggers(
                    playbook_klass=klass,
                    playbook_signature=signature,
                    triggers=[
                        child.get("text", "").strip() for child in h3["children"]
                    ],
                )
            elif h3_title == "steps":
                steps = h3
                # Parse steps into PlaybookStep objects
                for child in h3.get("children", []):
                    lines = child.get("text", "").strip().split("\n")
                    for line in lines:
                        step = PlaybookStep.from_text(line)
                        if step:
                            step_collection.add_step(step)
            elif h3_title == "notes":
                notes = h3
            else:
                raise ValueError(f"Unknown H3 section: {h3_title}")

        return cls(
            klass=klass,
            execution_type=PlaybookExecutionType.MARKDOWN,
            signature=signature,
            description=description,
            triggers=triggers,
            steps=steps,
            notes=notes,
            code=None,
            func=None,
            markdown=h2["markdown"],
            step_collection=step_collection,
            export=export,
        )

    @classmethod
    def parse_title(cls, title: str) -> Tuple[str, str]:
        """Parse the title of a playbook.

        Args:
            title: The title of the playbook, e.g. "CheckOrderStatusFlow($authToken: str) -> None"

        Returns:
            A tuple containing the signature and class name.

        Raises:
            ValueError: If the class name is not a valid identifier.
        """
        export = False
        match = re.match(r"^export\s*:\s*(.*)", title, re.DOTALL)
        if match:
            export = True
            title = match.group(1).strip()

        # Extract the class name (must be a valid identifier starting with a letter)
        match = re.match(r"^[A-Za-z][A-Za-z0-9]*", title)
        if not match:
            raise ValueError(
                f"Playbook class name must be alphanumeric and start with a letter, got {title}"
            )

        klass = match.group(0)
        return title, klass, export

    def __init__(
        self,
        klass: str,
        execution_type: PlaybookExecutionType,
        signature: str,
        description: Optional[str],
        triggers: Optional[PlaybookTriggers],
        steps: Optional[Dict[str, Any]],
        notes: Optional[Dict[str, Any]],
        code: Optional[str],
        func: Optional[Callable],
        markdown: str,
        step_collection: Optional[PlaybookStepCollection] = None,
        export: bool = False,
    ):
        """Initialize a Playbook.

        Args:
            klass: The class name of the playbook.
            execution_type: The execution type (MD or PYTHON).
            signature: The signature of the playbook function.
            description: The description of the playbook.
            triggers: The triggers for the playbook.
            steps: The AST node representing the steps section.
            notes: The AST node representing the notes section.
            code: The Python code for PYTHON playbooks.
            func: The compiled function for PYTHON playbooks.
            markdown: The markdown representation of the playbook.
            step_collection: The collection of steps for MD playbooks.
        """
        self.klass = klass
        self.execution_type = execution_type
        self.signature = signature
        self.description = description
        self.triggers = triggers
        self.steps = steps
        self.notes = notes
        self.code = code
        self.func = func
        self.markdown = markdown
        self.step_collection = step_collection
        self.export = export

    def get_step(self, line_number: str) -> Optional[PlaybookStep]:
        """Get a step by line number.

        Args:
            line_number: The line number of the step.

        Returns:
            The step or None if not found.
        """
        if self.step_collection:
            return self.step_collection.get_step(line_number)
        return None

    def get_next_step(self, line_number: str) -> Optional[PlaybookStep]:
        """Get the next step after the given line number.

        Args:
            line_number: The line number to start from.

        Returns:
            The next step or None if there is no next step.
        """
        if self.step_collection:
            return self.step_collection.get_next_step(line_number)
        return None

    def trigger_instructions(self) -> List[str]:
        """Get the trigger instructions for the playbook.

        Returns:
            A list of trigger instruction strings, or an empty list if no triggers.
        """
        return (
            [str(trigger) for trigger in self.triggers.triggers]
            if self.triggers
            else []
        )

    def __repr__(self) -> str:
        """Return a string representation of the playbook."""
        return f"Playbook({self.klass})"

    def __str__(self) -> str:
        """Return the markdown representation of the playbook."""
        return self.markdown
