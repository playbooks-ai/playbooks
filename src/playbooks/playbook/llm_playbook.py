"""LLM playbooks that execute natural language programs on LLMs."""

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from playbooks.compilation.parse_utils import parse_metadata_and_description
from playbooks.core.enums import LLMExecutionMode
from playbooks.execution.playbook import PlaybookLLMExecution
from playbooks.execution.raw import RawLLMExecution
from playbooks.execution.react import ReActLLMExecution
from playbooks.execution.step import PlaybookStep, PlaybookStepCollection
from playbooks.playbook.local import LocalPlaybook
from playbooks.triggers import PlaybookTriggers


class LLMPlaybook(LocalPlaybook):
    """Natural language playbooks that execute on LLMs.

    LLM playbooks are written in natural language and parsed from markdown files.
    They can execute in three modes:
    - playbook: Traditional step-by-step execution with explicit steps
    - react: Looping execution until exit conditions are met
    - raw: Direct LLM call without structure
    """

    @classmethod
    def create_playbooks_from_h1(
        cls, h1: Dict, namespace_manager
    ) -> Dict[str, "LLMPlaybook"]:
        """Create LLMPlaybook instances from H1 AST node.

        Args:
            h1: H1 AST node containing agent definition
            namespace_manager: Namespace manager for setting up execution context

        Returns:
            Dict[str, LLMPlaybook]: Dictionary of created playbooks
        """
        playbooks = {}

        for child in h1["children"]:
            if child.get("type") == "h2":
                playbook = cls.from_h2(child)

                # Add call-through wrapper to namespace if agent is available
                agent = namespace_manager.namespace.get("agent")
                if agent is not None:
                    call_through = playbook.create_namespace_function(agent)
                    namespace_manager.namespace[playbook.name] = call_through

                playbooks[playbook.name] = playbook

        return playbooks

    def create_agent_specific_function(self, agent):
        """Create an agent-specific function that bypasses globals lookup."""

        async def agent_specific_wrapper(*args, _agent=agent, **kwargs):
            return await self.execute_with_agent(_agent, *args, **kwargs)

        return agent_specific_wrapper

    @classmethod
    def from_h2(cls, h2: Dict[str, Any]) -> "LLMPlaybook":
        """Create an LLMPlaybook from an H2 AST node.

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

        # Create LLM playbook
        return cls._create_llm_playbook(h2, klass, signature, description, h3s)

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
    def _create_llm_playbook(
        cls,
        h2: Dict[str, Any],
        klass: str,
        signature: str,
        description: Optional[str],
        h3s: List[Dict[str, Any]],
    ) -> "LLMPlaybook":
        """Create an LLM playbook.

        Args:
            h2: The H2 AST node.
            klass: The playbook class name.
            signature: The playbook signature.
            description: The playbook description.
            h3s: The list of H3 sections.

        Returns:
            A new LLM playbook instance.

        Raises:
            ValueError: If an unknown H3 section is encountered.
        """
        triggers = cls._parse_triggers(klass, signature, h3s)
        steps = cls._parse_steps(h3s)
        notes = cls._parse_notes(h3s)

        # Parse metadata from description
        metadata, cleaned_description = parse_metadata_and_description(
            description or ""
        )

        return cls(
            klass=klass,
            signature=signature,
            description=cleaned_description,
            triggers=triggers,
            steps=steps,
            notes=notes,
            code=None,
            func=None,
            markdown=h2["markdown"],
            step_collection=steps,
            metadata=metadata,
            source_line_number=h2.get("line_number"),
            source_file_path=h2.get("source_file_path"),
        )

    @classmethod
    def _parse_triggers(
        cls,
        klass: str,
        signature: str,
        h3s: List[Dict[str, Any]],
    ) -> PlaybookTriggers:
        """Parse the triggers from the H3 sections."""
        for h3 in h3s:
            h3_title = h3.get("text", "").strip().lower()
            if h3_title == "triggers":
                trigger_items = []
                trigger_line_numbers = []
                for child in h3["children"]:
                    if child.get("type") == "list":
                        for list_item in child.get("children", []):
                            if list_item.get("type") == "list-item":
                                trigger_items.append(list_item.get("text", "").strip())
                                trigger_line_numbers.append(
                                    list_item.get("line_number")
                                )
                return PlaybookTriggers(
                    playbook_klass=klass,
                    playbook_signature=signature,
                    triggers=trigger_items,
                    trigger_line_numbers=trigger_line_numbers,
                    source_line_number=h3.get("line_number"),
                )
        return None

    @classmethod
    def _parse_steps(cls, h3s: List[Dict[str, Any]]) -> PlaybookStepCollection:
        def parse_node(
            node: Dict[str, Any], step_collection: PlaybookStepCollection
        ) -> PlaybookStep:
            step = None
            if node.get("type") == "list-item":
                text = node.get("text", "").strip()
                item_line_number = node.get("line_number")
                source_file_path = node.get("source_file_path")
                step = PlaybookStep.from_text(text)
                if step:
                    step.source_line_number = item_line_number
                    step.source_file_path = source_file_path
                    step_collection.add_step(step)

                    if node.get("children"):
                        if len(node.get("children")) > 1:
                            raise ValueError(
                                f"Expected 1 child for list-item, got {len(node.get('children'))}"
                            )

                        list = node.get("children")[0]
                        if list.get("type") != "list":
                            raise ValueError(
                                f"Expected a single list under list-item, got a {list.get('type')}"
                            )

                        child_steps = []
                        for child in list.get("children", []):
                            child_step = parse_node(child, step_collection)
                            if child_step:
                                child_steps.append(child_step)

                        step.children = child_steps
            else:
                raise ValueError(f"Expected a list-item, got a {node.get('type')}")
            return step

        """Parse the steps from the H3 sections."""
        for h3 in h3s:
            h3_title = h3.get("text", "").strip().lower()
            if h3_title == "steps":
                step_collection = PlaybookStepCollection()
                if h3["children"] and "children" in h3["children"][0]:
                    for child in h3["children"][0]["children"]:
                        parse_node(child, step_collection)
                return step_collection
        return None

    @classmethod
    def _parse_notes(cls, h3s: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Parse the notes from the H3 sections."""
        for h3 in h3s:
            h3_title = h3.get("text", "").strip().lower()
            if h3_title == "notes":
                return h3
        return None

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
        signature: str,
        description: Optional[str],
        triggers: Optional[PlaybookTriggers],
        steps: Optional[Dict[str, Any]],
        notes: Optional[Dict[str, Any]],
        code: Optional[str],
        func: Optional[Callable],
        markdown: str,
        step_collection: Optional[PlaybookStepCollection] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source_file_path: Optional[str] = None,
        source_line_number: Optional[int] = None,
    ):
        """Initialize an LLMPlaybook.

        Args:
            klass: The class name of the playbook.
            signature: The signature of the playbook function.
            description: The description of the playbook.
            triggers: The triggers for the playbook.
            steps: The AST node representing the steps section.
            notes: The AST node representing the notes section.
            code: The Python code for PYTHON playbooks.
            func: The compiled function for PYTHON playbooks.
            markdown: The markdown representation of the playbook.
            step_collection: The collection of steps for LLM playbooks.
            metadata: Metadata dict.
            source_file_path: The file path of the source markdown where this
                playbook is defined.
            source_line_number: The line number in the source markdown where this
                playbook is defined.
        """
        # Parse metadata and description, merging with provided metadata
        parsed_metadata, parsed_description = parse_metadata_and_description(
            description or ""
        )
        merged_metadata = {**(metadata or {}), **parsed_metadata}
        final_description = parsed_description or description

        # Initialize parent with the new interface
        super().__init__(
            name=klass,
            description=final_description,
            agent_name=None,  # Will be set by the agent
            metadata=merged_metadata,
            source_file_path=source_file_path,
            source_line_number=source_line_number,
        )

        # Keep existing attributes for backward compatibility
        self.klass = klass
        self.signature = signature
        self.triggers = triggers
        self.steps = steps
        self.notes = notes
        self.code = code
        self.func = func
        self.markdown = markdown
        self.step_collection = step_collection

        # Set execution mode from metadata
        # Default to REACT if no steps and no execution_mode specified
        if "execution_mode" not in merged_metadata:
            default_mode = (
                LLMExecutionMode.REACT
                if step_collection is None
                else LLMExecutionMode.PLAYBOOK
            )
        else:
            default_mode = LLMExecutionMode.PLAYBOOK

        self.execution_mode = LLMExecutionMode(
            merged_metadata.get("execution_mode", default_mode)
        )

    async def execute_with_agent(self, agent, *args, **kwargs) -> Any:
        """Execute the LLM playbook using the specified agent.

        Args:
            agent: The agent to execute with
            *args: Positional arguments for the playbook
            **kwargs: Keyword arguments for the playbook

        Returns:
            The result of executing the playbook
        """
        # Create appropriate execution strategy
        if self.execution_mode == LLMExecutionMode.PLAYBOOK:
            execution = PlaybookLLMExecution(agent, self)
        elif self.execution_mode == LLMExecutionMode.REACT:
            execution = ReActLLMExecution(agent, self)
        else:  # RAW
            execution = RawLLMExecution(agent, self)

        return await execution.execute(*args, **kwargs)

    async def _execute_impl(self, *args, **kwargs) -> Any:
        """Execute the LLM playbook using the compiled function.

        Args:
            *args: Positional arguments for the playbook
            **kwargs: Keyword arguments for the playbook

        Returns:
            The result of executing the playbook function
        """
        if not self.func:
            raise ValueError(f"Playbook {self.name} has no executable function")

        # Execute the compiled function
        return await self.func(*args, **kwargs)

    def get_parameters(self) -> Dict[str, Any]:
        """Get the parameters schema for this playbook.

        Returns:
            A dictionary describing the expected parameters based on the signature
        """
        # For now, return a basic schema based on the signature
        # This could be enhanced to parse the actual signature and extract parameter types
        return {
            "signature": self.signature,
            "description": f"Parameters for {self.name} playbook",
        }

    def get_description(self) -> str:
        """Get a human-readable description of this playbook.

        Returns:
            The description of the playbook
        """
        return self.description or self.name

    @property
    def first_step(self) -> Optional[PlaybookStep]:
        """Get the first step of the playbook."""
        if self.step_collection and len(self.step_collection.ordered_line_numbers) > 0:
            return self.step_collection.get_step(
                self.step_collection.ordered_line_numbers[0]
            )
        return None

    @property
    def first_step_line_number(self) -> Optional[int]:
        """Get the line number of the first step of the playbook."""
        if self.first_step:
            return self.first_step.source_line_number
        return self.source_line_number

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

    def __repr__(self) -> str:
        """Return a string representation of the playbook."""
        return f"LLMPlaybook({self.klass})"

    def __str__(self) -> str:
        """Return the markdown representation of the playbook."""
        return self.markdown
