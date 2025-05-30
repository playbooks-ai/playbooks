import os
from typing import Iterator

import frontmatter
from rich.console import Console

from .exceptions import ProgramLoadError
from .utils.langfuse_helper import LangfuseHelper
from .utils.llm_config import LLMConfig
from .utils.llm_helper import get_completion, get_messages_for_prompt
from .utils.markdown_to_ast import (
    parse_markdown_to_dict,
    refresh_markdown_attributes,
)

console = Console()


class Compiler:
    """
    Compiles Markdown playbooks into a format with line types and numbers for processing.

    The Compiler uses LLM to preprocess playbook content by adding line type codes,
    line numbers, and other metadata that enables the interpreter to understand the
    structure and flow of the playbook. It acts as a preprocessing step before the
    playbook is converted to an AST and executed.

    It validates basic playbook requirements before compilation, including checking
    for required headers that define agent name and playbook structure.
    """

    def __init__(self, llm_config: LLMConfig) -> None:
        """
        Initialize the compiler with LLM configuration.

        Args:
            llm_config: Configuration for the language model
        """
        self.llm_config = llm_config

    def preprocess_program(self, program_content: str) -> str:
        """
        Preprocess the program content by adding missing steps sections where needed.

        This method analyzes the markdown structure and automatically adds a "Steps"
        section to any H2 sections that don't already have one, using a template
        from react_steps.pb.

        Args:
            program_content: Raw program content with frontmatter

        Returns:
            str: Preprocessed program content
        """
        edited = False
        # Strip out the frontmatter
        frontmatter_data = frontmatter.loads(program_content)
        program_content = frontmatter_data.content
        frontmatter_data.content = ""
        ast = parse_markdown_to_dict(program_content)
        h2s = filter(
            lambda child: child["type"] == "h2",
            ast.get("children", []),
        )
        for h2 in h2s:
            h3s = list(
                filter(
                    lambda child: child["type"] == "h3"
                    and child.get("text", "").strip().lower() == "steps",
                    h2.get("children", []),
                )
            )
            if not h3s:
                with open(
                    os.path.join(
                        os.path.dirname(__file__), "prompts", "react_steps.pb"
                    ),
                    "r",
                ) as f:
                    react_steps = f.read()
                    steps_h3 = parse_markdown_to_dict(react_steps)
                    h2["children"].append(steps_h3)
                    edited = True

        if edited:
            refresh_markdown_attributes(ast)
            program_content = ast["markdown"]
            if len(frontmatter_data.metadata) > 0:
                program_content = frontmatter.dumps(frontmatter_data) + program_content

        return program_content

    def process(self, program_content: str) -> str:
        """
        Compile a string of Markdown playbooks by preprocessing and adding line type codes and line numbers.

        Args:
            program_content: Content of the playbooks

        Returns:
            str: Compiled content of the playbooks

        Raises:
            ProgramLoadError: If the playbook format is invalid
        """
        # First, preprocess the program content
        preprocessed_content = self.preprocess_program(program_content)

        # Basic validation of playbook format
        if not preprocessed_content.strip():
            raise ProgramLoadError("Empty playbook content")

        # Check for required H1 and H2 headers
        lines = preprocessed_content.split("\n")
        found_h1 = False
        found_h2 = False

        for line in lines:
            if line.startswith("# "):
                found_h1 = True
            elif line.startswith("## ") or "@playbook" in line:
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

        prompt = prompt.replace("{{PLAYBOOKS}}", preprocessed_content)
        messages = get_messages_for_prompt(prompt)
        langfuse_span = LangfuseHelper.instance().trace(
            name="compile_playbooks", input=preprocessed_content
        )

        # Get the compiled content from the LLM
        response: Iterator[str] = get_completion(
            llm_config=self.llm_config,
            messages=messages,
            stream=False,
            langfuse_span=langfuse_span,
        )

        processed_content = next(response)
        langfuse_span.update(output=processed_content)
        console.print("[dim pink]Compiled playbook content[/dim pink]")

        return processed_content
