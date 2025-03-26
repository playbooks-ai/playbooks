import ast
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from .enums import PlaybookExecutionType
from .playbook_step import PlaybookStep, PlaybookStepCollection
from .utils.markdown_to_ast import refresh_markdown_attributes


class PlaybookTrigger:
    """Represents a trigger that can start a playbook."""

    def __init__(
        self, playbook_klass: str, playbook_signature: str, list_item: Dict[str, Any]
    ):
        """Initialize a PlaybookTrigger.

        Args:
            playbook_klass: The class name of the playbook.
            playbook_signature: The signature of the playbook function.
            list_item: The AST node representing the trigger in the markdown.
        """
        self.playbook_klass = playbook_klass
        self.playbook_signature = playbook_signature
        self.list_item = list_item
        self.text = list_item.get("text", "").strip()
        # Example text: "- 01:BGN When the agent starts running"
        self.trigger_name = self.text.split(" ")[0]
        self.trigger_description = " ".join(self.text.split(" ")[1:])

    def __str__(self) -> str:
        """Return a string representation of the trigger."""
        signature = self.playbook_signature.split(" ->")[0]
        return f'- {self.trigger_description}, `Trigger["{self.playbook_klass}:{self.trigger_name}"]` by enqueuing `{signature}`'


class PlaybookTriggers:
    """Collection of triggers for a playbook."""

    def __init__(
        self, playbook_klass: str, playbook_signature: str, h3: Dict[str, Any]
    ):
        """Initialize a PlaybookTriggers collection.

        Args:
            playbook_klass: The class name of the playbook.
            playbook_signature: The signature of the playbook function.
            h3: The AST node representing the triggers section.
        """
        self.playbook_klass = playbook_klass
        self.playbook_signature = playbook_signature
        self.h3 = h3
        self.triggers = [
            PlaybookTrigger(
                playbook_klass=self.playbook_klass,
                playbook_signature=self.playbook_signature,
                list_item=item,
            )
            for item in h3.get("children", [])
        ]


class Playbook:
    """Represents a playbook that can be executed by an agent.

    Playbooks can be of two types:
    - INT: Internal playbooks written in the step format.
    - EXT: External playbooks written in Python code.
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
        signature, klass = cls.parse_title(h2.get("text", "").strip())
        description, h3s = cls._extract_description_and_h3s(h2)

        # Determine playbook type based on presence of a Code h3 section
        if any(h3.get("text", "").strip().lower() == "code" for h3 in h3s):
            # External playbook (EXT)
            playbook = cls._create_ext_playbook(h2, klass, signature, description, h3s)
            # Refresh markdown attributes after removing code sections
            refresh_markdown_attributes(h2)
            playbook.markdown = h2["markdown"]
            return playbook
        else:
            # Internal playbook (INT)
            return cls._create_int_playbook(h2, klass, signature, description, h3s)

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
    def _process_code_block(cls, code: Optional[str]) -> Tuple[str, Callable]:
        """Process and validate a Python code block.

        Args:
            code: The Python code as a string.

        Returns:
            A tuple containing the processed code and the compiled function.

        Raises:
            ValueError: If the code is None, contains multiple functions, or no functions.
        """
        if code is None:
            raise ValueError("EXT playbook must have a code block")

        code = code.strip()

        # Parse and validate python code
        tree = ast.parse(code)
        module_globals = {}
        func = None

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if func is not None:
                    raise ValueError(
                        "Multiple functions found in EXT playbook. Each EXT playbook should have a single function."
                    )

                code_obj = compile(
                    ast.Module(body=[node], type_ignores=[]),
                    filename="<ast>",
                    mode="exec",
                )
                exec(code_obj, module_globals)
                func = module_globals[node.name]
                break

        if func is None:
            raise ValueError(
                "No function found in EXT playbook. Each EXT playbook should have a single function."
            )

        return code, func

    @classmethod
    def _create_int_playbook(
        cls,
        h2: Dict[str, Any],
        klass: str,
        signature: str,
        description: Optional[str],
        h3s: List[Dict[str, Any]],
    ) -> "Playbook":
        """Create an internal (INT) type playbook.

        Args:
            h2: The H2 AST node.
            klass: The playbook class name.
            signature: The playbook signature.
            description: The playbook description.
            h3s: The list of H3 sections.

        Returns:
            A new INT playbook instance.

        Raises:
            ValueError: If an unknown H3 section is encountered.
        """
        trigger = None
        steps = None
        notes = None
        step_collection = PlaybookStepCollection()

        for h3 in h3s:
            h3_title = h3.get("text", "").strip().lower()
            if h3_title == "trigger":
                trigger = PlaybookTriggers(
                    playbook_klass=klass, playbook_signature=signature, h3=h3
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
            execution_type=PlaybookExecutionType.INT,
            signature=signature,
            description=description,
            trigger=trigger,
            steps=steps,
            notes=notes,
            code=None,
            func=None,
            markdown=h2["markdown"],
            step_collection=step_collection,
        )

    @classmethod
    def _create_ext_playbook(
        cls,
        h2: Dict[str, Any],
        klass: str,
        signature: str,
        description: Optional[str],
        h3s: List[Dict[str, Any]],
    ) -> "Playbook":
        """Create an external (EXT) type playbook.

        Args:
            h2: The H2 AST node.
            klass: The playbook class name.
            signature: The playbook signature.
            description: The playbook description.
            h3s: The list of H3 sections.

        Returns:
            A new EXT playbook instance.

        Raises:
            ValueError: If EXT playbook has sections other than 'code' or the code block is invalid.
        """
        code = None
        for h3 in h3s:
            h3_title = h3.get("text", "").strip().lower()
            if h3_title == "code":
                code_block = h3.get("children", [{}])[0]
                if code_block.get("type") != "code-block":
                    raise ValueError(
                        f"EXT playbook ### Code section can only have a code block, found: {h3.get('markdown', '')}"
                    )
                code = code_block["text"]
            else:
                raise ValueError(
                    f"EXT playbook can only have a code block, found: {h3_title}"
                )

            # Remove the code block from the markdown
            h2["children"].remove(h3)

        code, func = cls._process_code_block(code)

        return cls(
            klass=klass,
            execution_type=PlaybookExecutionType.EXT,
            signature=signature,
            description=description,
            trigger=None,
            steps=None,
            notes=None,
            code=code,
            func=func,
            markdown=h2["markdown"],
            step_collection=None,
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
        # Extract the class name (must be a valid identifier starting with a letter)
        match = re.match(r"^[A-Za-z][A-Za-z0-9]*", title)
        if not match:
            raise ValueError(
                f"Playbook class name must be alphanumeric and start with a letter, got {title}"
            )

        klass = match.group(0)
        return title, klass

    def __init__(
        self,
        klass: str,
        execution_type: PlaybookExecutionType,
        signature: str,
        description: Optional[str],
        trigger: Optional[PlaybookTriggers],
        steps: Optional[Dict[str, Any]],
        notes: Optional[Dict[str, Any]],
        code: Optional[str],
        func: Optional[Callable],
        markdown: str,
        step_collection: Optional[PlaybookStepCollection] = None,
    ):
        """Initialize a Playbook.

        Args:
            klass: The class name of the playbook.
            execution_type: The execution type (INT or EXT).
            signature: The signature of the playbook function.
            description: The description of the playbook.
            trigger: The triggers for the playbook.
            steps: The AST node representing the steps section.
            notes: The AST node representing the notes section.
            code: The Python code for EXT playbooks.
            func: The compiled function for EXT playbooks.
            markdown: The markdown representation of the playbook.
            step_collection: The collection of steps for INT playbooks.
        """
        self.klass = klass
        self.execution_type = execution_type
        self.signature = signature
        self.description = description
        self.trigger = trigger
        self.steps = steps
        self.notes = notes
        self.code = code
        self.func = func
        self.markdown = markdown
        self.step_collection = step_collection

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
            [str(trigger) for trigger in self.trigger.triggers] if self.trigger else []
        )

    def __repr__(self) -> str:
        """Return a string representation of the playbook."""
        return f"Playbook({self.klass})"

    def __str__(self) -> str:
        """Return the markdown representation of the playbook."""
        return self.markdown
