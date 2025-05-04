from glob import glob
from pathlib import Path
from typing import List

from .exceptions import ProgramLoadError


class Loader:
    @staticmethod
    def read_program(program_paths: List[str]) -> str:
        """
        Load program content from file paths.
        """
        program_content = None
        try:
            program_content = Loader._read_program(program_paths)
        except FileNotFoundError as e:
            raise ProgramLoadError(f"File not found: {str(e)}") from e
        except (OSError, IOError) as e:
            raise ProgramLoadError(f"Error reading file: {str(e)}") from e

        return program_content

    @staticmethod
    def _read_program(paths: List[str]) -> str:
        """
        Load program content from file paths. Supports both single files and glob patterns.

        Args:
            paths: List of file paths or glob patterns (e.g., 'my_playbooks/**/*.md')

        Returns:
            str: Combined contents of all matching program files

        Raises:
            FileNotFoundError: If no files are found or if files are empty
        """
        all_files = []

        for path in paths:
            # Simplified glob pattern check
            if "*" in str(path) or "?" in str(path) or "[" in str(path):
                # Handle glob pattern
                all_files.extend(glob.glob(path, recursive=True))
            else:
                # Handle single file
                all_files.append(path)

        if not all_files:
            raise FileNotFoundError("No files found")

        # Deduplicate files and read content
        contents = []
        for file in set(all_files):
            file_path = Path(file)
            if file_path.is_file():
                contents.append(file_path.read_text())

        program_contents = "\n\n".join(contents)

        if not program_contents:
            raise FileNotFoundError("Files found but content is empty")

        return program_contents
