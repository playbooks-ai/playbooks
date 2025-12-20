"""Module loader for in-process MCP servers.

This module provides utilities for loading MCP servers from Python files
and running them in-process using memory transport.
"""

import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

# Module-level cache for loaded server instances
_server_cache: Dict[str, Any] = {}


def parse_memory_url(url: str) -> Tuple[str, str]:
    """Parse a memory:// URL to extract file path and variable name.

    Args:
        url: Memory URL in format:
            - memory://path/to/server.py (uses default 'mcp' variable)
            - memory://path/to/server.py?var=custom_name
            - memory:///absolute/path/to/server.py

    Returns:
        Tuple of (file_path, var_name)

    Raises:
        ValueError: If URL format is invalid
    """
    if not url.startswith("memory://"):
        raise ValueError(f"Memory URL must start with 'memory://': {url}")

    # Parse the URL
    parsed = urlparse(url)

    # Extract file path (handle both //path and ///path for absolute paths)
    file_path = parsed.netloc + parsed.path if parsed.netloc else parsed.path

    # Extract variable name from query parameter, default to 'mcp'
    var_name = "mcp"
    if parsed.query:
        query_params = parse_qs(parsed.query)
        if "var" in query_params:
            var_name = query_params["var"][0]

    if not file_path:
        raise ValueError(f"Memory URL must contain a file path: {url}")

    logger.debug(f"Parsed memory URL: file_path={file_path}, var_name={var_name}")
    return file_path, var_name


def load_mcp_server(
    file_path: str,
    var_name: str = "mcp",
    force_reload: bool = False,
    base_dir: str = None,
) -> Any:
    """Load an MCP server instance from a Python file.

    Resolution strategy for relative paths:
    1. Relative to base_dir (playbook directory) - highest priority
    2. Relative to current working directory
    3. Relative to Python sys.path entries (for installed packages)

    This function loads a Python module and extracts the MCP server instance.
    Loaded servers are cached at the module level to ensure only one instance
    per file per session.

    Args:
        file_path: Path to the Python file containing the MCP server.
                  Relative paths are resolved using the priority above.
        var_name: Name of the variable containing the MCP server instance.
                 Defaults to 'mcp'.
        force_reload: If True, reload the module even if cached.
        base_dir: Base directory for resolving relative paths. When using memory
                 transport in playbooks, this is automatically set to the playbook
                 file's directory, making relative paths intuitive.

    Returns:
        The MCP server instance (typically a FastMCP object)

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the module doesn't contain the specified variable
        ImportError: If the module cannot be imported
    """
    original_file_path = Path(file_path)
    resolved_path = None
    search_paths = []

    # If absolute, use directly
    if original_file_path.is_absolute():
        resolved_path = original_file_path.resolve()
    else:
        # Build search path list
        if base_dir:
            search_paths.append(("playbook directory", Path(base_dir)))

        search_paths.append(("current working directory", Path(os.getcwd())))

        # Add sys.path entries (excluding empty strings and non-directory paths)
        for path_str in sys.path:
            if path_str and Path(path_str).is_dir():
                search_paths.append(("Python path", Path(path_str)))

        # Try each search path in order
        for location_name, search_path in search_paths:
            candidate = (search_path / original_file_path).resolve()
            if candidate.exists() and candidate.is_file():
                resolved_path = candidate
                logger.debug(
                    f"Found MCP server at: {resolved_path} "
                    f"(via {location_name}: {search_path})"
                )
                break

    # Check if file exists
    if not resolved_path or not resolved_path.exists():
        # Build detailed error message showing all locations searched
        search_info_lines = [
            f"  {i+1}. {name}: {path} -> {(path / original_file_path).resolve()}"
            for i, (name, path) in enumerate(search_paths)
        ]
        search_info = (
            "\n".join(search_info_lines)
            if search_info_lines
            else "  (no search paths available)"
        )

        raise FileNotFoundError(
            f"MCP server file not found: {file_path}\n"
            f"Searched in:\n{search_info}\n"
            f"Original file path: {file_path}"
        )

    if not resolved_path.is_file():
        raise ValueError(f"Path is not a file: {resolved_path}")

    # Check cache first
    cache_key = f"{resolved_path}:{var_name}"
    if not force_reload and cache_key in _server_cache:
        logger.debug(f"Using cached MCP server from {resolved_path}")
        return _server_cache[cache_key]

    # Load the module
    logger.info(f"Loading MCP server from {resolved_path}")

    try:
        # Create a module spec
        module_name = f"_mcp_server_{resolved_path.stem}_{id(resolved_path)}"
        spec = importlib.util.spec_from_file_location(module_name, resolved_path)

        if spec is None or spec.loader is None:
            raise ImportError(f"Failed to create module spec for {resolved_path}")

        # Load the module
        module = importlib.util.module_from_spec(spec)

        # Add to sys.modules to support relative imports within the module
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            # Clean up sys.modules on failure
            sys.modules.pop(module_name, None)
            raise ImportError(f"Failed to execute module {resolved_path}: {e}") from e

        # Extract the server instance
        if not hasattr(module, var_name):
            available_vars = [name for name in dir(module) if not name.startswith("_")]
            raise ValueError(
                f"Module {resolved_path} does not contain variable '{var_name}'.\n"
                f"Available variables: {', '.join(available_vars)}\n"
                f"Hint: Use '?var=your_variable_name' in the URL to specify a different variable."
            )

        server_instance = getattr(module, var_name)

        # Validate it looks like an MCP server
        # FastMCP instances have either 'get_server' method or are server instances themselves
        # We accept anything that looks like a server-like object (has common MCP attributes)
        if not (
            hasattr(server_instance, "get_server")
            or hasattr(server_instance, "mcp")
            or type(server_instance).__name__ == "FastMCP"
            or hasattr(server_instance, "list_tools")
        ):
            raise ValueError(
                f"Variable '{var_name}' in {resolved_path} does not appear to be an MCP server.\n"
                f"Expected a FastMCP instance or server object, got {type(server_instance).__name__}"
            )

        # Cache the server instance
        _server_cache[cache_key] = server_instance

        logger.info(f"Successfully loaded MCP server '{var_name}' from {resolved_path}")
        return server_instance

    except Exception as e:
        logger.error(f"Failed to load MCP server from {resolved_path}: {e}")
        raise


def get_server_instance(server: Any) -> Any:
    """Get the actual server instance from a FastMCP object.

    FastMCP objects may have a get_server() method that returns the underlying
    MCP server. This function handles both cases.

    Args:
        server: A FastMCP object or server instance

    Returns:
        The server instance suitable for passing to fastmcp.Client
    """
    if hasattr(server, "get_server"):
        return server.get_server()
    return server


def clear_cache() -> None:
    """Clear the module cache.

    This is primarily useful for testing or when you need to reload
    server definitions.
    """
    global _server_cache
    _server_cache.clear()
    logger.debug("Cleared MCP server cache")
