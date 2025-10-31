#!/usr/bin/env python3
"""
MCP Server for Deep Thinker System
Provides file operations, search, and utility functions.
"""

import hashlib
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("Deep Thinker Tools")

# Configuration
BASE_DIR = Path(".").resolve()
WORLD_MODEL_PATH = BASE_DIR / "world_model.md"
THINKING_SESSIONS_DIR = BASE_DIR / "thinking_sessions"
META_LOG_PATH = BASE_DIR / "meta_cognitive_log.jsonl"

# Ensure directories exist
THINKING_SESSIONS_DIR.mkdir(exist_ok=True)

# Security: Safe commands whitelist
SAFE_COMMANDS = {
    "ls",
    "cat",
    "grep",
    "wc",
    "head",
    "tail",
    "find",
    "pwd",
    "echo",
    "date",
    "whoami",
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def validate_path(path: str) -> bool:
    """
    Ensure path is within BASE_DIR and doesn't escape.

    Args:
        path: Path to validate

    Returns:
        True if path is safe
    """
    try:
        resolved = (BASE_DIR / path).resolve()
        return BASE_DIR in resolved.parents or resolved == BASE_DIR
    except Exception:
        return False


def safe_read_file(file_path: Path) -> str:
    """
    Safely read a file with error handling.

    Args:
        file_path: Path to file

    Returns:
        File contents or error message
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        # Try reading as binary and decoding with errors ignored
        with open(file_path, "rb") as f:
            return f.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {str(e)}"


# ============================================================================
# CORE FILE OPERATIONS
# ============================================================================


@mcp.tool
def read_file(path: str) -> str:
    """
    Read complete file contents.

    Args:
        path: Path to file to read (relative to base directory)

    Returns:
        File contents as string

    Examples:
        read_file("world_model.md")
        read_file("thinking_sessions/session_20251031_120000.md")
    """
    if not validate_path(path):
        logger.warning(f"Invalid path attempted: {path}")
        return f"Error: Invalid path {path}"

    file_path = BASE_DIR / path
    if not file_path.exists():
        logger.info(f"File not found: {path}")
        return f"Error: File {path} does not exist"

    if not file_path.is_file():
        return f"Error: {path} is not a file"

    logger.info(f"Reading file: {path}")
    return safe_read_file(file_path)


@mcp.tool
def write_file(path: str, content: str) -> str:
    """
    Write or overwrite a file with content.

    Args:
        path: Path to file (relative to base directory)
        content: Content to write

    Returns:
        Success message with character count

    Examples:
        write_file("test.txt", "Hello World")
        write_file("world_model.md", "# World Model\\n...")
    """
    if not validate_path(path):
        logger.warning(f"Invalid path attempted: {path}")
        return f"Error: Invalid path {path}"

    file_path = BASE_DIR / path
    file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Wrote {len(content)} characters to {path}")
        return f"Successfully wrote {len(content)} characters to {path}"
    except Exception as e:
        logger.error(f"Error writing file {path}: {e}")
        return f"Error writing file: {str(e)}"


@mcp.tool
def append_file(path: str, content: str) -> str:
    """
    Append content to a file.

    Args:
        path: Path to file (relative to base directory)
        content: Content to append

    Returns:
        Success message with character count

    Examples:
        append_file("world_model.md", "\\n## New Section\\n...")
        append_file("meta_cognitive_log.jsonl", '{"event": "..."}\\n')
    """
    if not validate_path(path):
        logger.warning(f"Invalid path attempted: {path}")
        return f"Error: Invalid path {path}"

    file_path = BASE_DIR / path
    file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Appended {len(content)} characters to {path}")
        return f"Successfully appended {len(content)} characters to {path}"
    except Exception as e:
        logger.error(f"Error appending to file {path}: {e}")
        return f"Error appending to file: {str(e)}"


@mcp.tool
def list_files(directory: str = ".") -> List[str]:
    """
    List files and directories in a directory.

    Args:
        directory: Directory to list (relative to base directory)

    Returns:
        List of filenames and directory names

    Examples:
        list_files(".")
        list_files("thinking_sessions")
    """
    if not validate_path(directory):
        logger.warning(f"Invalid path attempted: {directory}")
        return [f"Error: Invalid path {directory}"]

    dir_path = BASE_DIR / directory
    if not dir_path.exists():
        logger.info(f"Directory not found: {directory}")
        return [f"Error: Directory {directory} does not exist"]

    if not dir_path.is_dir():
        return [f"Error: {directory} is not a directory"]

    try:
        items = []
        for item in sorted(dir_path.iterdir()):
            rel_path = item.relative_to(BASE_DIR)
            if item.is_dir():
                items.append(f"{rel_path}/")
            else:
                items.append(str(rel_path))
        logger.info(f"Listed {len(items)} items in {directory}")
        return items
    except Exception as e:
        logger.error(f"Error listing directory {directory}: {e}")
        return [f"Error listing directory: {str(e)}"]


@mcp.tool
def ensure_directory(path: str) -> str:
    """
    Create directory if it doesn't exist.

    Args:
        path: Directory path (relative to base directory)

    Returns:
        Success message

    Examples:
        ensure_directory("thinking_sessions")
        ensure_directory("backups/2025")
    """
    if not validate_path(path):
        logger.warning(f"Invalid path attempted: {path}")
        return f"Error: Invalid path {path}"

    dir_path = BASE_DIR / path
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Directory ready: {path}")
        return f"Directory {path} ready"
    except Exception as e:
        logger.error(f"Error creating directory {path}: {e}")
        return f"Error creating directory: {str(e)}"


@mcp.tool
def get_file_stats(path: str) -> Dict[str, Any]:
    """
    Get file metadata and statistics.

    Args:
        path: Path to file (relative to base directory)

    Returns:
        Dictionary with file stats including size, created, modified times

    Examples:
        get_file_stats("world_model.md")
    """
    if not validate_path(path):
        logger.warning(f"Invalid path attempted: {path}")
        return {"error": f"Invalid path {path}"}

    file_path = BASE_DIR / path
    if not file_path.exists():
        return {"error": f"File {path} does not exist"}

    try:
        stat = file_path.stat()
        return {
            "path": path,
            "size": stat.st_size,
            "size_human": format_bytes(stat.st_size),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "is_file": file_path.is_file(),
            "is_directory": file_path.is_dir(),
        }
    except Exception as e:
        logger.error(f"Error getting stats for {path}: {e}")
        return {"error": str(e)}


def format_bytes(bytes: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes < 1024.0:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} TB"


# ============================================================================
# SEARCH OPERATIONS
# ============================================================================


@mcp.tool
def search_in_file(path: str, query: str) -> List[str]:
    """
    Search for text in a file and return matching lines with line numbers.

    Args:
        path: Path to file (relative to base directory)
        query: Text to search for (case-insensitive)

    Returns:
        List of matching lines with line numbers

    Examples:
        search_in_file("world_model.md", "emergence")
        search_in_file("thinking_sessions/session_123.md", "hypothesis")
    """
    if not validate_path(path):
        logger.warning(f"Invalid path attempted: {path}")
        return [f"Error: Invalid path {path}"]

    file_path = BASE_DIR / path
    if not file_path.exists():
        return [f"Error: File {path} does not exist"]

    if not file_path.is_file():
        return [f"Error: {path} is not a file"]

    try:
        matches = []
        content = safe_read_file(file_path)
        for line_num, line in enumerate(content.split("\n"), 1):
            if query.lower() in line.lower():
                matches.append(f"Line {line_num}: {line.strip()}")

        if not matches:
            return [f"No matches found for '{query}' in {path}"]

        logger.info(f"Found {len(matches)} matches for '{query}' in {path}")
        return matches
    except Exception as e:
        logger.error(f"Error searching file {path}: {e}")
        return [f"Error searching file: {str(e)}"]


@mcp.tool
def search_files(
    directory: str, query: str, pattern: str = "*.md"
) -> List[Dict[str, Any]]:
    """
    Search for text across multiple files in a directory.

    Args:
        directory: Directory to search (relative to base directory)
        query: Text to search for (case-insensitive)
        pattern: File pattern to match (default: "*.md")

    Returns:
        List of matches with file path, line number, and content

    Examples:
        search_files(".", "network effects")
        search_files("thinking_sessions", "hypothesis", "*.md")
    """
    if not validate_path(directory):
        logger.warning(f"Invalid path attempted: {directory}")
        return [{"error": f"Invalid path {directory}"}]

    dir_path = BASE_DIR / directory
    if not dir_path.exists():
        return [{"error": f"Directory {directory} does not exist"}]

    if not dir_path.is_dir():
        return [{"error": f"{directory} is not a directory"}]

    results = []
    try:
        # Search files matching pattern
        for file_path in dir_path.rglob(pattern):
            if not file_path.is_file():
                continue

            try:
                content = safe_read_file(file_path)
                for line_num, line in enumerate(content.split("\n"), 1):
                    if query.lower() in line.lower():
                        results.append(
                            {
                                "file": str(file_path.relative_to(BASE_DIR)),
                                "line": line_num,
                                "content": line.strip(),
                            }
                        )
            except Exception as e:
                logger.warning(f"Error reading {file_path}: {e}")
                continue

        if not results:
            return [{"message": f"No matches found for '{query}' in {directory}"}]

        logger.info(f"Found {len(results)} matches for '{query}' in {directory}")
        return results
    except Exception as e:
        logger.error(f"Error searching directory {directory}: {e}")
        return [{"error": str(e)}]


@mcp.tool
def grep_with_context(
    path: str, pattern: str, context_lines: int = 2
) -> List[Dict[str, Any]]:
    """
    Search file with context lines before and after matches.

    Args:
        path: Path to file (relative to base directory)
        pattern: Pattern to search for (case-insensitive)
        context_lines: Number of context lines before/after match (default: 2)

    Returns:
        List of matches with context

    Examples:
        grep_with_context("world_model.md", "principle", 2)
    """
    if not validate_path(path):
        logger.warning(f"Invalid path attempted: {path}")
        return [{"error": f"Invalid path {path}"}]

    file_path = BASE_DIR / path
    if not file_path.exists():
        return [{"error": f"File {path} does not exist"}]

    if not file_path.is_file():
        return [{"error": f"{path} is not a file"}]

    try:
        content = safe_read_file(file_path)
        lines = content.split("\n")

        matches = []
        for i, line in enumerate(lines):
            if pattern.lower() in line.lower():
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)

                context = {
                    "match_line": i + 1,
                    "match_content": line.strip(),
                    "context_before": [line.strip() for line in lines[start:i]],
                    "context_after": [line.strip() for line in lines[i + 1 : end]],
                }
                matches.append(context)

        if not matches:
            return [{"message": f"No matches found for '{pattern}' in {path}"}]

        logger.info(f"Found {len(matches)} matches for '{pattern}' in {path}")
        return matches
    except Exception as e:
        logger.error(f"Error searching file {path}: {e}")
        return [{"error": str(e)}]


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


@mcp.tool
def execute_command(command: str) -> str:
    """
    Execute a shell command (USE WITH CAUTION - whitelisted commands only).

    Args:
        command: Shell command to execute

    Returns:
        Command output or error message

    Examples:
        execute_command("ls -la")
        execute_command("wc -l world_model.md")

    Note:
        Only safe commands are allowed: ls, cat, grep, wc, head, tail, find, pwd, echo, date, whoami
    """
    cmd_name = command.split()[0] if command else ""

    if cmd_name not in SAFE_COMMANDS:
        logger.warning(f"Unsafe command attempted: {command}")
        return f"Error: Command '{cmd_name}' not in safe list. Allowed: {', '.join(sorted(SAFE_COMMANDS))}"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=BASE_DIR,
        )

        if result.returncode != 0:
            logger.warning(f"Command failed: {command}")
            return (
                f"Command failed with exit code {result.returncode}:\n{result.stderr}"
            )

        logger.info(f"Executed command: {command}")
        return result.stdout
    except subprocess.TimeoutExpired:
        logger.error(f"Command timeout: {command}")
        return "Error: Command timeout (10 seconds exceeded)"
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return f"Error executing command: {str(e)}"


@mcp.tool
def get_timestamp() -> str:
    """
    Get current timestamp in ISO format.

    Returns:
        Current timestamp string

    Examples:
        get_timestamp()  # Returns: "2025-10-31T14:30:45.123456"
    """
    timestamp = datetime.now().isoformat()
    logger.debug(f"Generated timestamp: {timestamp}")
    return timestamp


@mcp.tool
def hash_content(content: str) -> str:
    """
    Generate SHA-256 hash of content.

    Args:
        content: Content to hash

    Returns:
        Hex digest of hash

    Examples:
        hash_content("Hello World")
    """
    hash_value = hashlib.sha256(content.encode()).hexdigest()
    logger.debug(f"Generated hash for {len(content)} bytes")
    return hash_value


# ============================================================================
# WORLD MODEL SPECIFIC TOOLS
# ============================================================================


@mcp.tool
def initialize_world_model() -> str:
    """
    Initialize world model file with template structure if it doesn't exist.

    Returns:
        Success message

    Examples:
        initialize_world_model()
    """
    if WORLD_MODEL_PATH.exists():
        stats = get_file_stats.fn(str(WORLD_MODEL_PATH.relative_to(BASE_DIR)))
        logger.info("World model already exists")
        return f"World model already exists at {WORLD_MODEL_PATH.name} (size: {stats.get('size_human', 'unknown')})"

    template = f"""# World Model

## Meta
- Last updated: {datetime.now().isoformat()}
- Total concepts: 0
- Total principles: 0
- Total patterns: 0
- Total case studies: 0
- Confidence level: 0.0

## Core Principles
*Fundamental truths and axioms that enable broad predictions*

## Concept Graph
*Concepts and their relationships*

## Pattern Library
*Recurring dynamics and regularities*

## Case Studies
*Specific examples and applications*

## Predictions Enabled
*What we can now infer or forecast based on world model*

## Known Gaps
*What we don't understand yet*
"""

    try:
        with open(WORLD_MODEL_PATH, "w", encoding="utf-8") as f:
            f.write(template)
        logger.info(f"World model initialized at {WORLD_MODEL_PATH}")
        return f"World model initialized at {WORLD_MODEL_PATH.name}"
    except Exception as e:
        logger.error(f"Error initializing world model: {e}")
        return f"Error initializing world model: {str(e)}"


@mcp.tool
def get_world_model_stats() -> Dict[str, Any]:
    """
    Get statistics about the world model.

    Returns:
        Dictionary with stats including concept count, principle count, file size, last updated

    Examples:
        get_world_model_stats()
    """
    if not WORLD_MODEL_PATH.exists():
        logger.info("World model does not exist")
        return {
            "error": "World model does not exist",
            "hint": "Use initialize_world_model() to create it",
        }

    try:
        content = safe_read_file(WORLD_MODEL_PATH)

        # Count sections using markdown headers
        concept_count = len(re.findall(r"^### Concept:", content, re.MULTILINE))
        principle_count = len(re.findall(r"^### Principle:", content, re.MULTILINE))
        pattern_count = len(re.findall(r"^### Pattern:", content, re.MULTILINE))
        case_count = len(re.findall(r"^### Case:", content, re.MULTILINE))

        # Get file stats
        file_stats = get_file_stats.fn(str(WORLD_MODEL_PATH.relative_to(BASE_DIR)))

        stats = {
            "total_concepts": concept_count,
            "total_principles": principle_count,
            "total_patterns": pattern_count,
            "total_case_studies": case_count,
            "total_entries": concept_count
            + principle_count
            + pattern_count
            + case_count,
            "file_size": file_stats.get("size", 0),
            "file_size_human": file_stats.get("size_human", "0 B"),
            "last_updated": file_stats.get("modified", "unknown"),
            "line_count": len(content.split("\n")),
        }

        logger.info(f"World model stats: {stats['total_entries']} total entries")
        return stats
    except Exception as e:
        logger.error(f"Error getting world model stats: {e}")
        return {"error": str(e)}


@mcp.tool
def extract_world_model_section(section_name: str) -> str:
    """
    Extract a specific section from the world model.

    Args:
        section_name: Name of section to extract (e.g., "Core Principles", "Pattern Library")

    Returns:
        Section content or error message

    Examples:
        extract_world_model_section("Core Principles")
        extract_world_model_section("Pattern Library")
    """
    if not WORLD_MODEL_PATH.exists():
        return "Error: World model does not exist. Use initialize_world_model() first."

    try:
        content = safe_read_file(WORLD_MODEL_PATH)

        # Find section header (## Section Name)
        pattern = rf"^## {re.escape(section_name)}\s*$"
        matches = list(re.finditer(pattern, content, re.MULTILINE))

        if not matches:
            available_sections = re.findall(r"^## (.+)$", content, re.MULTILINE)
            return f"Section '{section_name}' not found. Available sections: {', '.join(available_sections)}"

        # Extract content from this section to next ## or end of file
        start = matches[0].end()
        next_section = re.search(r"^## ", content[start:], re.MULTILINE)

        if next_section:
            end = start + next_section.start()
            section_content = content[start:end].strip()
        else:
            section_content = content[start:].strip()

        logger.info(
            f"Extracted section '{section_name}' ({len(section_content)} chars)"
        )
        return section_content
    except Exception as e:
        logger.error(f"Error extracting section: {e}")
        return f"Error extracting section: {str(e)}"


# ============================================================================
# ADVANCED TOOLS (OPTIONAL)
# ============================================================================


@mcp.tool
def extract_concepts(text: str) -> List[str]:
    """
    Extract potential concepts from text (simple implementation).

    Args:
        text: Text to analyze

    Returns:
        List of potential concepts (capitalized phrases, technical terms)

    Examples:
        extract_concepts("Network effects and Emergence are key patterns")
    """
    # Extract capitalized words and phrases
    concepts = []

    # Find multi-word capitalized phrases
    multi_word = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text)
    concepts.extend(multi_word)

    # Find single capitalized words (but not at sentence start)
    words = text.split()
    for i, word in enumerate(words):
        # Skip first word and words after punctuation
        if i > 0 and words[i - 1][-1] not in ".!?":
            if word[0].isupper() and len(word) > 2:
                concepts.append(word.strip(".,;:()[]{}"))

    # Deduplicate while preserving order
    seen = set()
    unique_concepts = []
    for concept in concepts:
        if concept.lower() not in seen:
            seen.add(concept.lower())
            unique_concepts.append(concept)

    logger.debug(f"Extracted {len(unique_concepts)} concepts from text")
    return unique_concepts


@mcp.tool
def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate simple similarity between two texts using Jaccard similarity.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score (0-1)

    Examples:
        calculate_similarity("network effects matter", "network effects are important")
    """
    # Simple Jaccard similarity of word sets
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())

    intersection = len(words1 & words2)
    union = len(words1 | words2)

    if union == 0:
        return 0.0

    similarity = intersection / union
    logger.debug(f"Calculated similarity: {similarity:.3f}")
    return round(similarity, 3)


@mcp.tool
def count_lines(path: str) -> Dict[str, Any]:
    """
    Count lines in a file with breakdown by type.

    Args:
        path: Path to file (relative to base directory)

    Returns:
        Dictionary with line counts

    Examples:
        count_lines("world_model.md")
    """
    if not validate_path(path):
        return {"error": f"Invalid path {path}"}

    file_path = BASE_DIR / path
    if not file_path.exists():
        return {"error": f"File {path} does not exist"}

    try:
        content = safe_read_file(file_path)
        lines = content.split("\n")

        total_lines = len(lines)
        empty_lines = sum(1 for line in lines if not line.strip())
        comment_lines = sum(1 for line in lines if line.strip().startswith("#"))
        code_lines = total_lines - empty_lines

        result = {
            "total_lines": total_lines,
            "empty_lines": empty_lines,
            "non_empty_lines": total_lines - empty_lines,
            "header_lines": comment_lines,
            "content_lines": code_lines - comment_lines,
        }

        logger.info(f"Counted lines in {path}: {total_lines} total")
        return result
    except Exception as e:
        logger.error(f"Error counting lines: {e}")
        return {"error": str(e)}


# ============================================================================
# BATCH OPERATIONS
# ============================================================================


@mcp.tool
def batch_search(
    queries: List[str], directory: str = ".", pattern: str = "*.md"
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Search for multiple queries at once across files.

    Args:
        queries: List of search queries
        directory: Directory to search (relative to base directory)
        pattern: File pattern to match (default: "*.md")

    Returns:
        Dictionary mapping queries to their results

    Examples:
        batch_search(["emergence", "network effects", "principles"], ".")
    """
    results = {}

    for query in queries:
        results[query] = search_files.fn(directory, query, pattern)
        logger.debug(f"Batch search for '{query}': {len(results[query])} results")

    logger.info(f"Batch search completed for {len(queries)} queries")
    return results


@mcp.tool
def backup_file(path: str, backup_dir: str = "backups") -> str:
    """
    Create a timestamped backup of a file.

    Args:
        path: Path to file to backup (relative to base directory)
        backup_dir: Directory to store backups (default: "backups")

    Returns:
        Path to backup file or error message

    Examples:
        backup_file("world_model.md")
        backup_file("world_model.md", "backups/2025")
    """
    if not validate_path(path):
        return f"Error: Invalid path {path}"

    file_path = BASE_DIR / path
    if not file_path.exists():
        return f"Error: File {path} does not exist"

    # Create backup directory
    backup_path = BASE_DIR / backup_dir
    backup_path.mkdir(parents=True, exist_ok=True)

    # Create backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
    backup_file_path = backup_path / backup_name

    try:
        content = safe_read_file(file_path)
        with open(backup_file_path, "w", encoding="utf-8") as f:
            f.write(content)

        backup_rel = backup_file_path.relative_to(BASE_DIR)
        logger.info(f"Created backup: {backup_rel}")
        return f"Backup created at {backup_rel}"
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return f"Error creating backup: {str(e)}"


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    logger.info("Starting Deep Thinker MCP Server")
    logger.info(f"Base directory: {BASE_DIR}")
    logger.info(f"World model path: {WORLD_MODEL_PATH}")
    logger.info(f"Thinking sessions: {THINKING_SESSIONS_DIR}")

    # Run MCP server
    mcp.run(transport="streamable-http", port=8000)
