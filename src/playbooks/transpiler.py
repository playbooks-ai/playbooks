import os
from typing import Iterator

from rich.console import Console

from .exceptions import ProgramLoadError
from .utils.langfuse_helper import LangfuseHelper
from .utils.llm_config import LLMConfig
from .utils.llm_helper import get_completion, get_messages_for_prompt

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

    def process(self, program_content: str) -> str:
        """
        Transpile a string of Markdown playbooks by adding line type codes and line numbers.

        Args:
            program_content: Content of the playbooks

        Returns:
            str: Transpiled content of the playbooks

        Raises:
            ProgramLoadError: If the playbook format is invalid
        """
        # Basic validation of playbook format
        if not program_content.strip():
            raise ProgramLoadError("Empty playbook content")

        # Check for required H1 and H2 headers
        lines = program_content.split("\n")
        found_h1 = False
        found_h2 = False

        for line in lines:
            if line.startswith("# "):
                found_h1 = True
            elif line.startswith("## "):
                found_h2 = True

        if not found_h1:
            raise ProgramLoadError(
                "Failed to parse playbook: Missing H1 header (Agent name)"
            )
        if not found_h2:
            raise ProgramLoadError(
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
            raise ProgramLoadError(f"Error reading prompt template: {str(e)}") from e

        prompt = prompt.replace("{{PLAYBOOKS}}", program_content)
        messages = get_messages_for_prompt(prompt)
        langfuse_span = LangfuseHelper.instance().trace(
            name="transpile_playbooks", input=program_content
        )

        # Get the transpiled content from the LLM
        response: Iterator[str] = get_completion(
            llm_config=self.llm_config,
            messages=messages,
            stream=False,
            langfuse_span=langfuse_span,
        )

        processed_content = next(response)
        langfuse_span.update(output=processed_content)
        console.print("[dim pink]Transpiled playbook content[/dim pink]")

        return processed_content
