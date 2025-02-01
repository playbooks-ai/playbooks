import os

from playbooks.config import LLMConfig
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
        """

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

        processed_content = list(response)[0]

        # print("Processed content:")
        # print(processed_content)
        # print("=" * 40)

        return processed_content
