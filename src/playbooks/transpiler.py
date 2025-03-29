import os
from typing import Iterator

from rich.console import Console

from playbooks.config import LLMConfig
from playbooks.exceptions import PlaybookError
from playbooks.utils.llm_helper import get_completion, get_messages_for_prompt

console = Console()


class Transpiler:
    """
    Transpiles Markdown playbooks into a format with line types and numbers for processing.

    The Transpiler uses LLM to preprocess playbook content by adding line type codes,
    line numbers, and other metadata that enables the interpreter to understand the
    structure and flow of the playbook. It acts as a preprocessing step before the
    playbook is converted to an AST and executed.

    It validates basic playbook requirements before transpilation, including checking
    for required headers that define agent name and playbook structure.
    """

    def __init__(self, llm_config: LLMConfig) -> None:
        """
        Initialize the transpiler with LLM configuration.

        Args:
            llm_config: Configuration for the language model
        """
        self.llm_config = llm_config

    def process(self, playbooks_content: str) -> str:
        """
        Transpile a string of Markdown playbooks by adding line type codes and line numbers.

        Args:
            playbooks_content: Content of the playbooks

        Returns:
            str: Transpiled content of the playbooks

        Raises:
            PlaybookError: If the playbook format is invalid
        """
        # Basic validation of playbook format
        if not playbooks_content.strip():
            raise PlaybookError("Empty playbook content")

        # Check for required H1 and H2 headers
        lines = playbooks_content.split("\n")
        found_h1 = False
        found_h2 = False

        for line in lines:
            if line.startswith("# "):
                found_h1 = True
            elif line.startswith("## "):
                found_h2 = True

        if not found_h1:
            raise PlaybookError(
                "Failed to parse playbook: Missing H1 header (Agent name)"
            )
        if not found_h2:
            raise PlaybookError(
                "Failed to parse playbook: Missing H2 header (Playbook definition)"
            )

        # Load and prepare the prompt template
        prompt_path = os.path.join(
            os.path.dirname(__file__), "prompts/preprocess_playbooks.txt"
        )
        try:
            with open(prompt_path, "r") as f:
                prompt = f.read()
        except (IOError, OSError) as e:
            raise PlaybookError(f"Error reading prompt template: {str(e)}") from e

        prompt = prompt.replace("{{PLAYBOOKS}}", playbooks_content)
        messages = get_messages_for_prompt(prompt)

        # Get the transpiled content from the LLM
        response: Iterator[str] = get_completion(
            llm_config=self.llm_config,
            messages=messages,
            stream=False,
        )

        processed_content = next(response)
        console.print("[dim pink]Transpiled playbook content[/dim pink]")

        return processed_content
