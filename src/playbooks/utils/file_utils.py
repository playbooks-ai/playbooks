"""
Utility functions for file handling and type detection.
"""

from pathlib import Path
from typing import List


def is_compiled_playbook_file(file_path: str) -> bool:
    """
    Check if a file is a compiled playbook (.pbc) file.

    Args:
        file_path: Path to the file to check

    Returns:
        bool: True if the file is a .pbc file, False otherwise
    """
    return Path(file_path).suffix.lower() == ".pbc"


def is_source_playbook_file(file_path: str) -> bool:
    """
    Check if a file is a source playbook (.pb or .playbooks) file.

    Args:
        file_path: Path to the file to check

    Returns:
        bool: True if the file is a source playbook file, False otherwise
    """
    suffix = Path(file_path).suffix.lower()
    return suffix in [".pb", ".playbooks"]


def is_playbook_file(file_path: str) -> bool:
    """
    Check if a file is any type of playbook file (.pb, .pbc, .playbooks).

    Args:
        file_path: Path to the file to check

    Returns:
        bool: True if the file is a playbook file, False otherwise
    """
    return is_source_playbook_file(file_path) or is_compiled_playbook_file(file_path)


def has_compiled_playbook_files(file_paths: List[str]) -> bool:
    """
    Check if any of the provided file paths are compiled playbook files.

    Args:
        file_paths: List of file paths to check

    Returns:
        bool: True if any file is a .pbc file, False otherwise
    """
    return any(is_compiled_playbook_file(path) for path in file_paths)


def get_file_type_description(file_path: str) -> str:
    """
    Get a human-readable description of the file type.

    Args:
        file_path: Path to the file

    Returns:
        str: Description of the file type
    """
    if is_compiled_playbook_file(file_path):
        return "compiled playbook"
    elif is_source_playbook_file(file_path):
        return "source playbook"
    else:
        return "unknown file type"
