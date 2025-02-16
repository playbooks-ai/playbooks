import os

from playbooks.config import LLMConfig
from playbooks.exceptions import PlaybookError
from playbooks.utils.llm_helper import get_completion


class Transpiler:
    def __init__(self, llm_config: LLMConfig) -> None:
        self.llm_config = llm_config

    def process(self, playbooks_content: str) -> str:
        """Transpile a string of Markdown playbooks."""
        """
        Transpiles the playbooks content by adding line type code to each line, adding line numbers, etc.

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

        prompt = open(
            os.path.join(os.path.dirname(__file__), "prompts/preprocess_playbooks.txt"),
            "r",
        ).read()
        prompt = prompt.replace("{{PLAYBOOKS}}", playbooks_content)

        response = get_completion(
            llm_config=self.llm_config,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )

        response = list(response)
        processed_content = response[0]
        return processed_content
