import glob
from pathlib import Path
from typing import List

from .config import LLMConfig
from .exceptions import PlaybookError
from .transpiler import Transpiler
from .utils.markdown_to_ast import markdown_to_ast


class PlaybookLoader:
    """Handles loading playbook files and parsing them into Markdown AST."""

    @staticmethod
    def load_and_parse(playbooks_paths: List[str], llm_config: LLMConfig) -> dict:
        """
        Load playbooks from files and parse them into AST.

        Args:
            playbooks_paths: List of file paths or glob patterns

        Returns:
            dict: Parsed AST representation of the playbooks

        Raises:
            PlaybookError: If there are issues reading or parsing the playbooks
        """
        try:
            playbooks_content = PlaybookLoader.gather_playbooks(playbooks_paths)
        except FileNotFoundError as e:
            raise PlaybookError(f"Playbook not found: {str(e)}") from e
        except (OSError, IOError) as e:
            raise PlaybookError(f"Error reading playbook: {str(e)}") from e

        # Transpile playbooks
        transpiler = Transpiler(llm_config=llm_config)
        transpiled_content = transpiler.process(playbooks_content)
        return markdown_to_ast(transpiled_content)

    @staticmethod
    def gather_playbooks(paths: List[str]) -> str:
        """
        Load playbook(s) from file paths. Supports both single files and glob patterns.

        Args:
            paths: List of file paths or glob patterns (e.g., 'my_playbooks/**/*.md')

        Returns:
            str: Combined contents of all matching playbook files

        Raises:
            FileNotFoundError: If no files are found or if files are empty
        """
        all_files = []

        for path in paths:
            if any(char in path for char in ["*", "?", "["]):
                # Handle glob pattern
                all_files.extend(glob.glob(path, recursive=True))
            else:
                # Handle single file
                all_files.append(path)

        if not all_files:
            raise FileNotFoundError("No files found")

        contents = []
        for file in set(all_files):
            file_path = Path(file)
            if file_path.is_file():
                contents.append(file_path.read_text())

        combined_contents = "\n\n".join(contents)

        if not combined_contents:
            raise FileNotFoundError("No files found")

        return combined_contents
