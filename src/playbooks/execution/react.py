"""React execution that loops until exit conditions are met."""

from typing import TYPE_CHECKING, Any

from playbooks.compilation.compiler import Compiler
from playbooks.compilation.markdown_to_ast import markdown_to_ast
from playbooks.execution.step import PlaybookStep, PlaybookStepCollection

from .playbook import PlaybookLLMExecution

if TYPE_CHECKING:
    pass


class ReActLLMExecution(PlaybookLLMExecution):
    """React execution that loops until exit conditions are met.

    This mode enables the LLM to repeatedly:
    - Think about the current state
    - Decide on actions (tool calls, user interaction)
    - Execute those actions
    - Check exit conditions
    - Continue or complete
    """

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute with react looping behavior.

        Adds react loop steps if the playbook doesn't have steps defined,
        then delegates to parent's playbook execution.

        Args:
            *args: Positional arguments for the playbook
            **kwargs: Keyword arguments for the playbook

        Returns:
            Return value from the playbook execution (if any)
        """
        # Add react loop steps if not present
        if not self._has_steps():
            await self._add_react_steps()

        # Delegate to parent's playbook execution
        return await super().execute(*args, **kwargs)

    def _has_steps(self) -> bool:
        """Check if the playbook has steps defined."""
        return (
            hasattr(self.playbook, "step_collection")
            and self.playbook.step_collection
            and len(self.playbook.step_collection.ordered_line_numbers) > 0
        )

    async def _add_react_steps(self) -> None:
        """Add react loop steps to the playbook."""
        # Create a ReactAgent playbook for compilation
        react_playbook = """# ReactAgent

## ReactSteps
### Steps
- Think deeply about the $task to understand requirements
- Write down $exit_conditions for the task
- While $exit_conditions are not met:
  - Analyze current state and progress
  - Decide what action to take next
  - Execute the action (tool call, user interaction, computation)
  - Evaluate results against exit conditions
- Return final results
"""

        # Compile the playbook to get proper step structure
        compiled_steps = await self._compile_and_extract_steps(react_playbook)

        # Set the compiled step collection on the playbook
        self.playbook.step_collection = compiled_steps

    async def _compile_and_extract_steps(
        self, playbook_content: str
    ) -> PlaybookStepCollection:
        """Compile the playbook content and extract step collection.

        Args:
            playbook_content: The markdown playbook content to compile

        Returns:
            PlaybookStepCollection: The compiled step collection
        """
        try:
            compiler = Compiler()

            # Compile the playbook content
            _, compiled_content, _ = await compiler.compile(content=playbook_content)

            # Parse the compiled content to extract steps
            ast = markdown_to_ast(compiled_content)

            # Find the ReactAgent H1 section
            react_agent_h1 = None
            for child in ast.get("children", []):
                if child.get("type") == "h1" and "ReactAgent" in child.get("text", ""):
                    react_agent_h1 = child
                    break

            if not react_agent_h1:
                # Fallback to original behavior if compilation failed
                return self._create_fallback_steps()

            # Find the ReactSteps H2 section within the ReactAgent
            react_steps_h2 = None
            for child in react_agent_h1.get("children", []):
                if child.get("type") == "h2" and "ReactSteps" in child.get("text", ""):
                    react_steps_h2 = child
                    break

            if not react_steps_h2:
                # Fallback to original behavior if H2 not found
                return self._create_fallback_steps()

            # Extract steps from the compiled H2 section
            return self._extract_steps_from_h2(react_steps_h2)

        except Exception as e:
            # If any error occurs during compilation or parsing,
            # fall back to the original implementation
            raise Exception(f"Error creating react steps: {e}") from e

    def _extract_steps_from_h2(self, h2_node: dict) -> PlaybookStepCollection:
        """Extract steps from a compiled H2 node.

        Args:
            h2_node: The H2 AST node containing steps

        Returns:
            PlaybookStepCollection: The extracted step collection
        """

        def parse_node(
            node: dict, step_collection: PlaybookStepCollection
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

                        list_node = node.get("children")[0]
                        if list_node.get("type") != "list":
                            raise ValueError(
                                f"Expected a single list under list-item, got a {list_node.get('type')}"
                            )

                        child_steps = []
                        for child in list_node.get("children", []):
                            child_step = parse_node(child, step_collection)
                            if child_step:
                                child_steps.append(child_step)

                        step.children = child_steps
            else:
                raise ValueError(f"Expected a list-item, got a {node.get('type')}")
            return step

        # Find the Steps H3 section
        for child in h2_node.get("children", []):
            if (
                child.get("type") == "h3"
                and child.get("text", "").strip().lower() == "steps"
            ):
                step_collection = PlaybookStepCollection()
                if child["children"] and "children" in child["children"][0]:
                    for list_item in child["children"][0]["children"]:
                        parse_node(list_item, step_collection)
                return step_collection

        # No steps found, return empty collection
        return PlaybookStepCollection()
