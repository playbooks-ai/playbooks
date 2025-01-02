import glob
from pathlib import Path
from typing import List


def load(paths: List[str]) -> str:
    """
    Load playbook(s) from file path. Supports both single files and glob patterns.

    Args:
        path: File path or glob pattern (e.g., 'my_playbooks/**/*.md')

    Returns:
        str: Combined contents of all matching playbook files
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
        file = Path(file)
        if file.is_file():
            contents.append(file.read_text())

    contents = "\n\n".join(contents)

    if not contents:
        raise FileNotFoundError("No files found")

    return contents
