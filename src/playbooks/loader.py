from glob import glob
from pathlib import Path
from typing import List

from .exceptions import ProgramLoadError
from .utils.file_utils import is_compiled_playbook_file


class Loader:
    @staticmethod
    def read_program(program_paths: List[str]) -> str:
        """
        Load program content from file paths.
        """
        program_content = None
        try:
            program_content, do_not_compile = Loader._read_program(program_paths)
        except FileNotFoundError as e:
            raise ProgramLoadError(str(e)) from e
        except (OSError, IOError) as e:
            raise ProgramLoadError(str(e)) from e

        return program_content, do_not_compile

    @staticmethod
    def _read_program(paths: List[str]) -> str:
        """
        Load program content from file paths. Supports both single files and glob patterns.

        Args:
            paths: List of file paths or glob patterns (e.g., 'my_playbooks/**/*.pb')

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
                all_files.extend(glob(path, recursive=True))
            else:
                # Handle single file
                all_files.append(path)

        if not all_files:
            raise FileNotFoundError("No files found")

        # Deduplicate files and read content
        contents = []
        do_not_compile = False
        not_found = []
        for file in set(all_files):
            file_path = Path(file)
            if file_path.is_file() and file_path.exists():
                if is_compiled_playbook_file(file_path):
                    do_not_compile = True
                contents.append(file_path.read_text())
            else:
                not_found.append(str(file_path))

        if not_found:
            raise FileNotFoundError(f"{', '.join(not_found)} not found")

        program_contents = "\n\n".join(contents)

        if not program_contents:
            raise FileNotFoundError("Files found but content is empty")

        return program_contents, do_not_compile
