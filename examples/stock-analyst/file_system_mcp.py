"""
MCP Server for File System related tools
"""

import argparse
import os
import re
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from fastmcp import FastMCP

mcp = FastMCP("File System Tools")

# Default allowed directories for safe file writing
DEFAULT_ALLOWED_DIRS = [
    tempfile.gettempdir(),  # System temp directory
    os.getcwd(),  # Current working directory
    os.path.dirname(os.path.abspath(__file__)),  # MCP server directory
]


@mcp.tool
def validate_directory(path: str) -> Dict:
    """
    Validate that the specified path is a directory and exists and contains at least one markdown file (recursive listing).

    Args:
        path: Directory path to validate

    Returns:
        Dictionary with validation result
    """
    try:
        path_obj = Path(path)
        if not path_obj.exists():
            return {"error": f"Path does not exist: {path}"}
        if not path_obj.is_dir():
            return {"error": f"Path is not a directory: {path}"}
        if not any(path_obj.glob("*.md")):
            return {"error": f"Path does not contain any markdown files: {path}"}
        return {
            "success": True,
            "markdown_file_count": len(list(path_obj.glob("*.md"))),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def list_directory(path: str, recursive: bool = False) -> Dict:
    """
    List files and directories in the specified path.

    Args:
        path: Directory path to list
        recursive: If True, recursively list all subdirectories

    Returns:
        Dictionary with directory structure and file information
    """
    try:
        path_obj = Path(path)
        if not path_obj.exists():
            return {"error": f"Path does not exist: {path}"}

        if not path_obj.is_dir():
            return {"error": f"Path is not a directory: {path}"}

        files_info = []

        if recursive:
            for root, dirs, files in os.walk(path):
                # Filter to .md files
                for file in sorted(files):
                    if file.endswith(".md"):
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, path)
                        stat = os.stat(full_path)
                        files_info.append(
                            {
                                "name": file,
                                "path": full_path,
                                "rel_path": rel_path,
                                "size_bytes": stat.st_size,
                                "modified": stat.st_mtime,
                                "is_dir": False,
                            }
                        )
        else:
            for item in sorted(os.listdir(path)):
                full_path = os.path.join(path, item)
                stat = os.stat(full_path)
                files_info.append(
                    {
                        "name": item,
                        "path": full_path,
                        "size_bytes": stat.st_size,
                        "modified": stat.st_mtime,
                        "is_dir": os.path.isdir(full_path),
                    }
                )

        return {
            "path": path,
            "recursive": recursive,
            "files": files_info,
            "count": len(files_info),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def get_file_info(filepath: str) -> Dict:
    """
    Get detailed information about a markdown file.

    Args:
        filepath: Path to the file

    Returns:
        File metadata including line count, headings, etc.
    """
    try:
        path_obj = Path(filepath)
        if not path_obj.exists():
            return {"error": f"File does not exist: {filepath}"}

        stat = os.stat(filepath)

        # Count lines
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
            line_count = len(lines)

        # Extract headings (table of contents)
        headings = []
        for i, line in enumerate(lines, 1):
            if line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                title = line.lstrip("#").strip()
                headings.append({"line": i, "level": level, "title": title})

        return {
            "filepath": filepath,
            "name": path_obj.name,
            "size_bytes": stat.st_size,
            "line_count": line_count,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "headings": headings,
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def grep_files(directory: str, pattern: str, file_extension: str = ".md") -> Dict:
    """
    Search for a pattern in files within a directory.

    Args:
        directory: Directory to search
        pattern: Regex pattern to search for
        file_extension: File extension to search (default: .md)

    Returns:
        Dictionary with search results
    """
    try:
        results = []
        pattern_re = re.compile(pattern, re.IGNORECASE)

        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith(file_extension):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            for line_num, line in enumerate(f, 1):
                                if pattern_re.search(line):
                                    results.append(
                                        {
                                            "filepath": filepath,
                                            "line": line_num,
                                            "content": line.strip(),
                                        }
                                    )
                    except Exception:
                        pass

        return {
            "directory": directory,
            "pattern": pattern,
            "matches_count": len(results),
            "results": results[:100],  # Limit to 100 results
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def get_file_hierarchy(directory: str) -> Dict:
    """
    Get a hierarchical structure of all markdown files in a directory.

    Args:
        directory: Root directory to analyze

    Returns:
        Hierarchical file structure with metadata
    """
    try:
        structure = {}

        for root, dirs, files in os.walk(directory):
            md_files = [f for f in files if f.endswith(".md")]

            if md_files:
                rel_path = os.path.relpath(root, directory)
                if rel_path == ".":
                    rel_path = "root"

                structure[rel_path] = []

                for file in sorted(md_files):
                    full_path = os.path.join(root, file)
                    stat = os.stat(full_path)

                    # Get headings
                    with open(full_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()

                    headings = []
                    for i, line in enumerate(lines, 1):
                        if line.startswith("# ") or line.startswith("## "):
                            level = len(line) - len(line.lstrip("#"))
                            title = line.lstrip("#").strip()
                            if level <= 2:
                                headings.append({"level": level, "title": title})

                    structure[rel_path].append(
                        {
                            "name": file,
                            "path": full_path,
                            "lines": len(lines),
                            "size_bytes": stat.st_size,
                            "main_sections": headings[:5],  # First 5 headings
                        }
                    )

        return {"directory": directory, "structure": structure}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def read_file(filepath: str) -> str:
    """
    Read the contents of a file.

    Args:
        filepath: Path to the file

    Returns:
        File contents
    """
    try:
        path_obj = Path(filepath)
        if not path_obj.exists():
            return {"error": f"File does not exist: {filepath}"}
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def read_file_line_ranges(filepath: str, ranges: Optional[List[tuple]] = None) -> Dict:
    """
    Read one or more line ranges from a file.

    Args:
        filepath: Path to the markdown file
        ranges: Optional list of tuples (start_line, end_line) in 1-indexed format.
                If None or empty, reads the entire file.

    Returns:
        Dictionary with line range contents
    """
    try:
        path_obj = Path(filepath)
        if not path_obj.exists():
            return {"error": f"File does not exist: {filepath}"}

        with open(filepath, "r", encoding="utf-8") as f:
            all_lines = f.readlines()

        total_lines = len(all_lines)

        # If no ranges specified, return entire file
        if not ranges:
            content = "".join(all_lines)
            return {
                "filepath": filepath,
                "start_line": 1,
                "end_line": total_lines,
                "total_lines": total_lines,
                "lines_read": total_lines,
                "content": content,
                "is_full_file": True,
                "ranges": None,
            }

        # Process multiple ranges
        range_contents = []
        for start_line, end_line in ranges:
            # Validate and normalize ranges
            start_line = max(1, start_line)
            end_line = min(total_lines, end_line)

            if start_line > total_lines:
                return {
                    "error": f"Start line {start_line} exceeds file length {total_lines}"
                }

            # Extract lines (convert from 1-indexed to 0-indexed)
            selected_lines = all_lines[start_line - 1 : end_line]
            content = "".join(selected_lines)

            range_contents.append(
                {
                    "start_line": start_line,
                    "end_line": end_line,
                    "lines_read": len(selected_lines),
                    "content": content,
                    "range_path": f"{filepath}--{start_line}-{end_line}.md",
                }
            )

        return {
            "filepath": filepath,
            "total_lines": total_lines,
            "num_ranges": len(range_contents),
            "ranges": range_contents,
            "is_full_file": False,
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def extract_table_of_contents(filepath: str) -> Dict:
    """
    Extract table of contents from a markdown file with line ranges for each section.

    Returns structured information about headings with their line numbers and
    calculated line ranges (from heading to start of next heading or end of file).
    This enables efficient content loading using read_file_with_ranges.

    Args:
        filepath: Path to the markdown file

    Returns:
        Dictionary with structured table of contents including line ranges
    """
    try:
        path_obj = Path(filepath)
        if not path_obj.exists():
            return {"error": f"File does not exist: {filepath}"}

        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        line_count = len(lines)

        # Extract headings (table of contents)
        headings = []
        for i, line in enumerate(lines, 1):
            if line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                title = line.lstrip("#").strip()
                headings.append({"line": i, "level": level, "title": title})

        # Calculate line ranges for each heading
        # Each heading's range extends from its line to the line before the next heading
        sections_with_ranges = []
        for idx, heading in enumerate(headings):
            start_line = heading["line"]
            # End line is either the line before next heading, or end of file
            if idx + 1 < len(headings):
                end_line = headings[idx + 1]["line"] - 1
            else:
                end_line = line_count

            sections_with_ranges.append(
                {
                    "line": heading["line"],
                    "level": heading["level"],
                    "title": heading["title"],
                    "start_line": start_line,
                    "end_line": end_line,
                    "section_size": end_line - start_line + 1,
                }
            )

        return {
            "filepath": filepath,
            "line_count": line_count,
            "headings": sections_with_ranges,
            "h1_count": sum(1 for h in sections_with_ranges if h["level"] == 1),
            "h2_count": sum(1 for h in sections_with_ranges if h["level"] == 2),
            "total_sections": len(sections_with_ranges),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def write_file(
    filepath: str, content: str, allowed_dirs: Optional[List[str]] = None
) -> Dict:
    """
    Write content to a file with safety checks.

    Safety features:
    - Path traversal protection
    - Directory whitelist (only writes to allowed directories)
    - Overwrite prevention (will not overwrite existing files)

    Args:
        filepath: Path to the file to write
        content: Content to write to the file
        allowed_dirs: Optional list of allowed directories. Defaults to:
                     - System temp directory
                     - Current working directory
                     - MCP server directory

    Returns:
        Dictionary with success status or error message
    """
    try:
        # Use default allowed directories if not specified
        if allowed_dirs is None:
            allowed_dirs = DEFAULT_ALLOWED_DIRS

        # Convert to Path object and resolve to absolute path
        # resolve() also resolves symlinks, preventing symlink-based path traversal
        filepath_obj = Path(filepath).resolve()

        # Check if file already exists - disallow overwriting
        if filepath_obj.exists():
            return {
                "error": f"File already exists: {filepath}. Overwriting is not allowed for safety."
            }

        # Normalize and resolve allowed directories
        allowed_dirs_resolved = [Path(d).resolve() for d in allowed_dirs]

        # Check if the resolved filepath is within one of the allowed directories
        is_allowed = False
        for allowed_dir in allowed_dirs_resolved:
            try:
                # Check if filepath is relative to allowed_dir
                # This will raise ValueError if filepath is not under allowed_dir
                filepath_obj.relative_to(allowed_dir)
                is_allowed = True
                break
            except ValueError:
                # Not under this allowed directory, try next
                continue

        if not is_allowed:
            allowed_dirs_str = "\n  - ".join(str(d) for d in allowed_dirs_resolved)
            return {
                "error": f"Path '{filepath_obj}' is outside allowed directories.\n"
                f"Allowed directories:\n  - {allowed_dirs_str}"
            }

        # Create parent directories if they don't exist (within allowed dirs)
        parent_dir = filepath_obj.parent
        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)

        # Write the file
        with open(filepath_obj, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "success": True,
            "filepath": str(filepath_obj),
            "bytes_written": len(content.encode("utf-8")),
        }

    except PermissionError as e:
        return {"error": f"Permission denied: {str(e)}"}
    except OSError as e:
        return {"error": f"OS error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


@mcp.tool
def create_directory(directory: str) -> Dict:
    """
    Create a directory.
    """
    try:
        Path(directory).mkdir(parents=True, exist_ok=True)
        return {"success": True, "directory": directory}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="File System MCP Server")
    parser.add_argument(
        "--port",
        type=int,
        default=8889,
        help="Port to run the server on (default: 8889)",
    )
    args = parser.parse_args()

    mcp.run(transport="streamable-http", port=args.port)
