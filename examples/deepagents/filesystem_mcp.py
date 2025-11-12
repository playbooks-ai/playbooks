"""
Filesystem MCP Server for DeepAgent Playbooks
Provides file system operations: ls, read_file, write_file, edit_file, glob, grep
"""

import re
import subprocess
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastmcp import FastMCP

mcp = FastMCP("Filesystem Tools")


@mcp.tool
def ls(path: str) -> Dict[str, Any]:
    """List files and directories in the specified directory (non-recursive).

    Args:
        path: Absolute directory path to list files from

    Returns:
        Dictionary with list of files and directories with metadata
    """
    try:
        path_obj = Path(path).resolve()

        if not path_obj.exists():
            return {"error": f"Path does not exist: {path}"}

        if not path_obj.is_dir():
            return {"error": f"Path is not a directory: {path}"}

        results = []
        for child in path_obj.iterdir():
            try:
                is_file = child.is_file()
                is_dir = child.is_dir()

                info = {
                    "path": str(child),
                    "name": child.name,
                    "is_dir": is_dir,
                }

                if is_file:
                    stat = child.stat()
                    info["size"] = stat.st_size
                    info["modified_at"] = stat.st_mtime

                results.append(info)
            except (OSError, PermissionError):
                continue

        results.sort(key=lambda x: x["path"])
        return {"path": path, "items": results, "count": len(results)}

    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def read_file(file_path: str, offset: int = 0, limit: int = 500) -> Dict[str, Any]:
    """Read file content with line numbers.

    Args:
        file_path: Absolute or relative file path
        offset: Line offset to start reading from (0-indexed)
        limit: Maximum number of lines to read

    Returns:
        Dictionary with file content and metadata
    """
    try:
        path = Path(file_path).resolve()

        if not path.exists() or not path.is_file():
            return {"error": f"File not found: {file_path}"}

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        if not content:
            return {"warning": "File exists but is empty", "content": ""}

        lines = content.splitlines()
        start_idx = offset
        end_idx = min(start_idx + limit, len(lines))

        if start_idx >= len(lines):
            return {
                "error": f"Line offset {offset} exceeds file length ({len(lines)} lines)"
            }

        selected_lines = lines[start_idx:end_idx]

        # Format with line numbers
        formatted_lines = []
        for i, line in enumerate(selected_lines, start=start_idx + 1):
            formatted_lines.append(f"{i:6d}|{line}")

        return {
            "file_path": file_path,
            "total_lines": len(lines),
            "start_line": start_idx + 1,
            "end_line": end_idx,
            "content": "\n".join(formatted_lines),
        }

    except Exception as e:
        return {"error": f"Error reading file: {str(e)}"}


@mcp.tool
def write_file(file_path: str, content: str) -> Dict[str, Any]:
    """Create a new file with content.

    Args:
        file_path: Path for the new file
        content: Content to write

    Returns:
        Result of the write operation
    """
    try:
        path = Path(file_path).resolve()

        if path.exists():
            return {
                "error": f"File already exists: {file_path}. Use edit_file to modify existing files."
            }

        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(content, encoding="utf-8")

        return {
            "success": True,
            "file_path": file_path,
            "message": f"Successfully created file: {file_path}",
        }

    except Exception as e:
        return {"error": f"Error writing file: {str(e)}"}


@mcp.tool
def edit_file(
    file_path: str, old_string: str, new_string: str, replace_all: bool = False
) -> Dict[str, Any]:
    """Edit a file by replacing string occurrences.

    Args:
        file_path: Path to the file to edit
        old_string: String to find and replace
        new_string: Replacement string
        replace_all: If True, replace all occurrences; if False, only first occurrence

    Returns:
        Result of the edit operation
    """
    try:
        path = Path(file_path).resolve()

        if not path.exists() or not path.is_file():
            return {"error": f"File not found: {file_path}"}

        content = path.read_text(encoding="utf-8")

        # Count occurrences
        count = content.count(old_string)

        if count == 0:
            return {"error": f"String not found in file: '{old_string[:50]}...'"}

        if not replace_all and count > 1:
            return {
                "error": f"String appears {count} times. Use replace_all=True to replace all occurrences, or provide a more specific string."
            }

        # Perform replacement
        if replace_all:
            new_content = content.replace(old_string, new_string)
            occurrences = count
        else:
            new_content = content.replace(old_string, new_string, 1)
            occurrences = 1

        path.write_text(new_content, encoding="utf-8")

        return {
            "success": True,
            "file_path": file_path,
            "occurrences": occurrences,
            "message": f"Successfully replaced {occurrences} occurrence(s)",
        }

    except Exception as e:
        return {"error": f"Error editing file: {str(e)}"}


@mcp.tool
def glob(pattern: str, path: str = ".") -> Dict[str, Any]:
    """Find files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., "*.py", "**/*.txt")
        path: Base directory to search from

    Returns:
        List of matching file paths
    """
    try:
        base_path = Path(path).resolve()

        if not base_path.exists():
            return {"error": f"Path does not exist: {path}"}

        # Use rglob for recursive patterns
        if "**" in pattern:
            pattern = pattern.replace("**/", "")
            matches = list(base_path.rglob(pattern))
        else:
            matches = list(base_path.glob(pattern))

        # Filter to files only
        file_paths = [str(p) for p in matches if p.is_file()]
        file_paths.sort()

        return {
            "pattern": pattern,
            "base_path": str(base_path),
            "matches": file_paths,
            "count": len(file_paths),
        }

    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def grep(
    pattern: str,
    path: Optional[str] = None,
    glob_pattern: Optional[str] = None,
    output_mode: str = "files_with_matches",
) -> Dict[str, Any]:
    """Search for a pattern in files.

    Args:
        pattern: Text pattern to search for (regex supported)
        path: Directory to search in (default: current directory)
        glob_pattern: Filter files by glob pattern (e.g., "*.py")
        output_mode: Output format - "files_with_matches", "content", or "count"

    Returns:
        Search results in the specified format
    """
    try:
        # Validate regex
        try:
            re.compile(pattern)
        except re.error as e:
            return {"error": f"Invalid regex pattern: {e}"}

        base_path = Path(path or ".").resolve()

        if not base_path.exists():
            return {"error": f"Path does not exist: {path}"}

        # Try using ripgrep first
        results = _ripgrep_search(pattern, base_path, glob_pattern, output_mode)

        if results is None:
            # Fallback to Python implementation
            results = _python_grep(pattern, base_path, glob_pattern, output_mode)

        return results

    except Exception as e:
        return {"error": str(e)}


def _ripgrep_search(
    pattern: str, base_path: Path, glob_pattern: Optional[str], output_mode: str
) -> Optional[Dict[str, Any]]:
    """Try to use ripgrep for faster searching."""
    try:
        cmd = ["rg", "--json"]

        if glob_pattern:
            cmd.extend(["--glob", glob_pattern])

        cmd.extend(["--", pattern, str(base_path)])

        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        )

        if proc.returncode not in [0, 1]:  # 1 means no matches found
            return None

        # Parse JSON output
        matches = {}
        for line in proc.stdout.splitlines():
            try:
                data = json.loads(line)
                if data.get("type") == "match":
                    file_path = data["data"]["path"]["text"]
                    line_num = data["data"]["line_number"]
                    line_text = data["data"]["lines"]["text"].rstrip("\n")

                    if file_path not in matches:
                        matches[file_path] = []
                    matches[file_path].append({"line": line_num, "text": line_text})
            except json.JSONDecodeError:
                continue

        return _format_grep_results(matches, output_mode)

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _python_grep(
    pattern: str, base_path: Path, glob_pattern: Optional[str], output_mode: str
) -> Dict[str, Any]:
    """Python fallback for grep."""
    try:
        regex = re.compile(pattern)
    except re.error:
        return {"error": "Invalid regex pattern"}

    matches = {}

    # Determine files to search
    if glob_pattern:
        if "**" in glob_pattern:
            files = base_path.rglob(glob_pattern.replace("**/", ""))
        else:
            files = base_path.glob(glob_pattern)
    else:
        files = base_path.rglob("*")

    for file_path in files:
        if not file_path.is_file():
            continue

        # Skip large files (> 10MB)
        try:
            if file_path.stat().st_size > 10 * 1024 * 1024:
                continue
        except OSError:
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
            for line_num, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    file_str = str(file_path)
                    if file_str not in matches:
                        matches[file_str] = []
                    matches[file_str].append({"line": line_num, "text": line})
        except (UnicodeDecodeError, PermissionError, OSError):
            continue

    return _format_grep_results(matches, output_mode)


def _format_grep_results(
    matches: Dict[str, List[Dict]], output_mode: str
) -> Dict[str, Any]:
    """Format grep results based on output mode."""
    if output_mode == "files_with_matches":
        return {"matches": list(matches.keys()), "count": len(matches)}
    elif output_mode == "count":
        counts = {file: len(lines) for file, lines in matches.items()}
        return {"counts": counts, "total_matches": sum(counts.values())}
    else:  # content
        formatted = []
        for file, lines in matches.items():
            for match in lines:
                formatted.append(
                    {"file": file, "line": match["line"], "text": match["text"]}
                )
        return {"matches": formatted, "count": len(formatted)}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
