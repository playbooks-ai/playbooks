import ast
import re
from typing import Callable, Optional, Tuple

from .enums import PlaybookExecutionType
from .playbook_step import PlaybookStep, PlaybookStepCollection
from .utils.markdown_to_ast import refresh_markdown_attributes


class Playbook:
    @classmethod
    def from_h2(cls, h2):
        """Create a Playbook from an H2 AST node.

        Args:
            h2: Dictionary representing an H2 AST node

        Returns:
            Playbook: A new playbook instance

        Raises:
            ValueError: If the H2 structure is invalid or required sections are missing
        """
        cls._validate_h2_structure(h2)
        signature, klass = cls.parse_title(h2.get("text", "").strip())
        description, h3s = cls._extract_description_and_h3s(h2)

        # If there is a Code h3, then this is an EXT playbook
        if any(h3.get("text", "").strip().lower() == "code" for h3 in h3s):
            ext_playbook = cls._create_ext_playbook(
                h2, klass, signature, description, h3s
            )
            # Python code blocks were removed from EXT playbooks,
            # so we need to refresh the markdown attributes
            refresh_markdown_attributes(h2)
            ext_playbook.markdown = h2["markdown"]
            return ext_playbook

        else:
            return cls._create_int_playbook(h2, klass, signature, description, h3s)

    @staticmethod
    def _validate_h2_structure(h2):
        """Verify no nested h1/h2s in the H2 node."""

        def check_no_nested_headers(node):
            for child in node.get("children", []):
                if child.get("type") in ["h1", "h2"]:
                    raise ValueError("H2 is not expected to have H1s or H2s")
                check_no_nested_headers(child)

        assert h2.get("type") == "h2"
        check_no_nested_headers(h2)

    @staticmethod
    def _extract_description_and_h3s(h2):
        """Extract description and h3 sections from H2 node."""
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
    def _process_code_block(cls, code):
        """Process and validate a code block."""
        if code is None:
            raise ValueError("EXT playbook must have a code block")

        # Clean up code block markers
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
    def _create_int_playbook(cls, h2, klass, signature, description, h3s):
        """Create an INT type playbook."""
        trigger = None
        steps = None
        notes = None
        step_collection = PlaybookStepCollection()

        for h3 in h3s:
            h3_title = h3.get("text", "").strip().lower()
            if h3_title == "trigger":
                trigger = h3
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
    def _create_ext_playbook(cls, h2, klass, signature, description, h3s):
        """Create an EXT type playbook."""
        code = None
        for h3 in h3s:
            h3_title = h3.get("text", "").strip().lower()
            if h3_title == "code":
                code_block = h3["children"][0]
                if code_block.get("type") != "code-block":
                    raise ValueError(
                        f"EXT playbook ### Code section can only have a code block, found: {h3['markdown']}"
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
            A tuple containing the class name (e.g. "CheckOrderStatusFlow") and the signature (e.g. "CheckOrderStatusFlow($authToken: str)")
        """
        # klass is the name of the playbook class, e.g. "CheckOrderStatusFlow" or "Playbook1"
        # klass is alphanumeric and starts with a letter. Find first non-alphanumeric character, if any, and split on that.
        match = re.match(r"^[A-Za-z][A-Za-z0-9]*", title)
        if not match:
            raise Exception(
                f"Playbook class name must be alphanumeric and start with a letter, got {title}"
            )

        klass = match.group(0)

        return title, klass

    def __init__(
        self,
        klass: str,
        execution_type: str,
        signature: str,
        description: str,
        trigger: dict,
        steps: dict,
        notes: dict,
        code: str,
        func: Callable,
        markdown: str,
        step_collection: Optional[PlaybookStepCollection] = None,
    ):
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

    def __repr__(self):
        return f"Playbook({self.klass})"

    def __str__(self):
        return self.markdown
