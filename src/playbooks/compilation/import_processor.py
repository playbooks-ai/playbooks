"""
Import processor for handling !import directives in Playbooks.

This module provides functionality to process import directives in playbook files,
resolving file paths, detecting circular dependencies, and preserving indentation.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from playbooks.infrastructure.logging.debug_logger import debug
from playbooks.core.exceptions import ProgramLoadError


class CircularImportError(ProgramLoadError):
    """Raised when a circular import dependency is detected."""

    def __init__(self, import_chain: List[Path]):
        self.import_chain = import_chain
        chain_str = " → ".join(str(p) for p in import_chain)
        super().__init__(f"Circular import detected: {chain_str}")


class ImportDepthError(ProgramLoadError):
    """Raised when maximum import nesting depth is exceeded."""

    def __init__(self, depth: int, max_depth: int, import_chain: List[Path]):
        self.depth = depth
        self.max_depth = max_depth
        self.import_chain = import_chain
        chain_str = " → ".join(str(p) for p in import_chain)
        super().__init__(
            f"Maximum import depth ({max_depth}) exceeded at depth {depth}. "
            f"Import chain: {chain_str}"
        )


class ImportNotFoundError(ProgramLoadError):
    """Raised when an imported file cannot be found."""

    def __init__(self, file_path: str, importing_file: Path, line_num: int):
        self.file_path = file_path
        self.importing_file = importing_file
        self.line_num = line_num
        super().__init__(
            f"Cannot import '{file_path}' - file not found\n"
            f"Location: {importing_file}, line {line_num}"
        )


class ImportProcessor:
    """Processes !import directives in playbook files."""

    # Regex pattern to match import directives
    IMPORT_PATTERN = re.compile(r"^(\s*)!import\s+(.+?)(?:\s*#.*)?$")

    # Default configuration
    DEFAULT_MAX_DEPTH = 10
    DEFAULT_MAX_FILE_SIZE = 1024 * 1024  # 1MB

    def __init__(
        self,
        base_path: Optional[Path] = None,
        max_depth: int = DEFAULT_MAX_DEPTH,
        max_file_size: int = DEFAULT_MAX_FILE_SIZE,
    ):
        """
        Initialize the import processor.

        Args:
            base_path: Base directory for resolving relative imports
            max_depth: Maximum nesting depth for imports
            max_file_size: Maximum size of imported files in bytes
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.max_depth = max_depth
        self.max_file_size = max_file_size

        # Track import state during processing
        self.import_stack: List[Path] = []
        self.processed_files: Dict[Path, str] = {}

    def process_imports(self, content: str, file_path: Path, depth: int = 0) -> str:
        """
        Process all import directives in the given content.

        Args:
            content: The content containing import directives
            file_path: Path of the file being processed
            depth: Current import depth (for recursion tracking)

        Returns:
            Processed content with imports inlined

        Raises:
            CircularImportError: If circular dependency detected
            ImportDepthError: If maximum nesting depth exceeded
            ImportNotFoundError: If imported file not found
        """
        # Check depth limit
        if depth > self.max_depth:
            raise ImportDepthError(depth, self.max_depth, self.import_stack)

        # Resolve to absolute path
        file_path = file_path.resolve()

        # Check for circular imports
        if file_path in self.import_stack:
            raise CircularImportError(self.import_stack + [file_path])

        # Add to import stack
        self.import_stack.append(file_path)

        try:
            # Process the content line by line
            lines = content.split("\n")
            result_lines = []

            for line_num, line in enumerate(lines, 1):
                match = self.IMPORT_PATTERN.match(line)

                if match:
                    # Extract indentation and import path
                    indentation = match.group(1)
                    import_path = match.group(2).strip()

                    # Process the import
                    imported_lines = self._process_single_import(
                        import_path, file_path, line_num, indentation, depth
                    )
                    result_lines.extend(imported_lines)
                else:
                    # Regular line - add as-is
                    result_lines.append(line)

            return "\n".join(result_lines)

        finally:
            # Remove from import stack
            self.import_stack.pop()

    def _process_single_import(
        self,
        import_path: str,
        importing_file: Path,
        line_num: int,
        indentation: str,
        depth: int,
    ) -> List[str]:
        """
        Process a single import directive.

        Args:
            import_path: Path specified in the import directive
            importing_file: File containing the import directive
            line_num: Line number of the import directive
            indentation: Indentation to apply to imported content
            depth: Current import depth

        Returns:
            List of processed lines from the imported file

        Raises:
            ImportNotFoundError: If imported file not found
        """
        # Resolve the import path
        resolved_path = self._resolve_import_path(import_path, importing_file)

        if not resolved_path:
            raise ImportNotFoundError(import_path, importing_file, line_num)

        # Check if file is already cached
        if resolved_path in self.processed_files:
            content = self.processed_files[resolved_path]
        else:
            # Read the file content
            content = self._read_file(resolved_path, importing_file, line_num)

            # Process nested imports recursively
            if "!import" in content:
                content = self.process_imports(content, resolved_path, depth + 1)

            # Cache the processed content
            self.processed_files[resolved_path] = content

        # Apply indentation to each line
        lines = content.split("\n")
        indented_lines = [
            indentation + line if line.strip() else line for line in lines
        ]

        return indented_lines

    def _resolve_import_path(
        self, import_path: str, importing_file: Path
    ) -> Optional[Path]:
        """
        Resolve an import path to an absolute file path.

        Args:
            import_path: Path specified in import directive
            importing_file: File containing the import

        Returns:
            Resolved absolute path or None if not found
        """
        # Check if it's a URL
        parsed = urlparse(import_path)
        if parsed.scheme in ("http", "https", "file"):
            # Handle URL imports (simplified for now)
            if parsed.scheme == "file":
                return Path(parsed.path)
            else:
                # For HTTP/HTTPS, would need to download and cache
                # Not implemented in MVP
                debug(f"URL imports not yet supported: {import_path}")
                return None

        # Convert to Path object
        path = Path(import_path)

        # Try different resolution strategies
        candidates = []

        # 1. Absolute path
        if path.is_absolute():
            candidates.append(path)
        else:
            # 2. Relative to importing file's directory
            candidates.append(importing_file.parent / path)

            # 3. Relative to base path
            candidates.append(self.base_path / path)

            # 4. Relative to current working directory
            candidates.append(Path.cwd() / path)

        # Check each candidate
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()

        return None

    def _read_file(self, file_path: Path, importing_file: Path, line_num: int) -> str:
        """
        Read content from a file with size validation.

        Args:
            file_path: Path to read
            importing_file: File that imports this file
            line_num: Line number of import directive

        Returns:
            File content as string

        Raises:
            ImportNotFoundError: If file cannot be read
            ProgramLoadError: If file exceeds size limit
        """
        try:
            # Check file size
            file_size = file_path.stat().st_size
            if file_size > self.max_file_size:
                raise ProgramLoadError(
                    f"Imported file '{file_path}' exceeds maximum size "
                    f"({file_size} > {self.max_file_size} bytes)"
                )

            # Read the file
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()

        except (IOError, OSError) as e:
            raise ImportNotFoundError(str(file_path), importing_file, line_num) from e

    def reset(self) -> None:
        """Reset the processor state for a new processing session.

        Clears the import stack and processed files cache.
        """
        self.import_stack.clear()
        self.processed_files.clear()
