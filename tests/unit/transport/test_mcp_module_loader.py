"""Unit tests for MCP module loader."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

from playbooks.transport.mcp_module_loader import (
    clear_cache,
    get_server_instance,
    load_mcp_server,
    parse_memory_url,
)


class TestParseMemoryUrl:
    """Tests for memory URL parsing."""

    def test_parse_simple_path(self):
        """Test parsing simple memory URL without query params."""
        file_path, var_name = parse_memory_url("memory://path/to/server.py")
        assert file_path == "path/to/server.py"
        assert var_name == "mcp"

    def test_parse_absolute_path(self):
        """Test parsing absolute path with three slashes."""
        file_path, var_name = parse_memory_url("memory:///absolute/path/to/server.py")
        assert file_path == "/absolute/path/to/server.py"
        assert var_name == "mcp"

    def test_parse_with_var_parameter(self):
        """Test parsing URL with custom variable name."""
        file_path, var_name = parse_memory_url("memory://path/to/server.py?var=custom")
        assert file_path == "path/to/server.py"
        assert var_name == "custom"

    def test_parse_absolute_with_var_parameter(self):
        """Test parsing absolute path with custom variable name."""
        file_path, var_name = parse_memory_url(
            "memory:///absolute/path/to/server.py?var=my_server"
        )
        assert file_path == "/absolute/path/to/server.py"
        assert var_name == "my_server"

    def test_parse_relative_path_with_dots(self):
        """Test parsing relative path with parent directory references."""
        file_path, var_name = parse_memory_url("memory://../parent/server.py")
        assert file_path == "../parent/server.py"
        assert var_name == "mcp"

    def test_invalid_scheme(self):
        """Test error on invalid URL scheme."""
        with pytest.raises(ValueError, match="must start with 'memory://'"):
            parse_memory_url("http://path/to/server.py")

    def test_empty_path(self):
        """Test error on empty file path."""
        with pytest.raises(ValueError, match="must contain a file path"):
            parse_memory_url("memory://")

    def test_multiple_query_params(self):
        """Test URL with multiple query parameters (only var is used)."""
        file_path, var_name = parse_memory_url(
            "memory://server.py?var=custom&other=ignored"
        )
        assert file_path == "server.py"
        assert var_name == "custom"


class TestLoadMcpServer:
    """Tests for MCP server loading."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_cache()

    def test_load_valid_server(self):
        """Test loading a valid MCP server file."""
        # Create a temporary MCP server file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(
                """
from fastmcp import FastMCP

mcp = FastMCP("TestServer")

@mcp.tool()
def test_tool(arg: str) -> str:
    return f"Result: {arg}"
"""
            )
            tmp_path = tmp.name

        try:
            server = load_mcp_server(tmp_path)
            assert server is not None
            # Verify it's a FastMCP instance
            assert type(server).__name__ == "FastMCP"
        finally:
            os.unlink(tmp_path)

    def test_load_with_custom_var_name(self):
        """Test loading server with custom variable name."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(
                """
from fastmcp import FastMCP

my_custom_server = FastMCP("TestServer")
"""
            )
            tmp_path = tmp.name

        try:
            server = load_mcp_server(tmp_path, var_name="my_custom_server")
            assert server is not None
        finally:
            os.unlink(tmp_path)

    def test_file_not_found(self):
        """Test error when file doesn't exist."""
        with pytest.raises(FileNotFoundError, match="MCP server file not found"):
            load_mcp_server("/nonexistent/path/server.py")

    def test_missing_variable(self):
        """Test error when specified variable doesn't exist."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(
                """
# File with no mcp variable
x = 42
"""
            )
            tmp_path = tmp.name

        try:
            with pytest.raises(ValueError, match="does not contain variable 'mcp'"):
                load_mcp_server(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_invalid_module_syntax(self):
        """Test error when module has syntax errors."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(
                """
# Invalid Python syntax
def broken(
"""
            )
            tmp_path = tmp.name

        try:
            with pytest.raises(ImportError, match="Failed to execute module"):
                load_mcp_server(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_caching_behavior(self):
        """Test that server instances are cached."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(
                """
from fastmcp import FastMCP

mcp = FastMCP("TestServer")
"""
            )
            tmp_path = tmp.name

        try:
            # Load once
            server1 = load_mcp_server(tmp_path)
            # Load again - should return same instance
            server2 = load_mcp_server(tmp_path)
            assert server1 is server2
        finally:
            os.unlink(tmp_path)

    def test_force_reload(self):
        """Test that force_reload bypasses cache."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(
                """
from fastmcp import FastMCP

mcp = FastMCP("TestServer")
counter = 0
"""
            )
            tmp_path = tmp.name

        try:
            # Load once
            server1 = load_mcp_server(tmp_path)
            # Force reload - may return different instance
            server2 = load_mcp_server(tmp_path, force_reload=True)
            # Both should be valid servers
            assert server1 is not None
            assert server2 is not None
        finally:
            os.unlink(tmp_path)

    def test_relative_path_resolution(self):
        """Test that relative paths are resolved from CWD."""
        # Create temp directory and file
        with tempfile.TemporaryDirectory() as tmpdir:
            server_file = Path(tmpdir) / "server.py"
            server_file.write_text(
                """
from fastmcp import FastMCP

mcp = FastMCP("TestServer")
"""
            )

            # Save original CWD
            orig_cwd = os.getcwd()
            try:
                # Change to temp directory
                os.chdir(tmpdir)
                # Load using relative path
                server = load_mcp_server("server.py")
                assert server is not None
            finally:
                # Restore CWD
                os.chdir(orig_cwd)

    def test_path_is_directory(self):
        """Test error when path is a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="Path is not a file"):
                load_mcp_server(tmpdir)

    def test_helpful_error_message_for_missing_var(self):
        """Test that error message suggests available variables."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(
                """
from fastmcp import FastMCP

server = FastMCP("TestServer")
other_var = "value"
"""
            )
            tmp_path = tmp.name

        try:
            with pytest.raises(ValueError) as exc_info:
                load_mcp_server(tmp_path)

            error_msg = str(exc_info.value)
            assert "Available variables:" in error_msg
            assert "server" in error_msg
            assert "other_var" in error_msg
            assert "?var=your_variable_name" in error_msg
        finally:
            os.unlink(tmp_path)


class TestGetServerInstance:
    """Tests for server instance extraction."""

    def test_get_server_with_method(self):
        """Test getting server from object with get_server method."""

        class MockServer:
            def get_server(self):
                return "actual_server"

        mock = MockServer()
        result = get_server_instance(mock)
        assert result == "actual_server"

    def test_get_server_without_method(self):
        """Test getting server from object without get_server method."""
        server = "direct_server"
        result = get_server_instance(server)
        assert result == "direct_server"


class TestClearCache:
    """Tests for cache clearing."""

    def test_clear_cache(self):
        """Test that clear_cache removes all cached servers."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(
                """
from fastmcp import FastMCP

mcp = FastMCP("TestServer")
"""
            )
            tmp_path = tmp.name

        try:
            # Load server to populate cache
            server1 = load_mcp_server(tmp_path)

            # Clear cache
            clear_cache()

            # Load again - should be a fresh load
            server2 = load_mcp_server(tmp_path)

            # Both should be valid
            assert server1 is not None
            assert server2 is not None
        finally:
            os.unlink(tmp_path)

    def test_search_priority_base_dir_wins(self):
        """Test that base_dir takes priority over CWD."""
        with (
            tempfile.TemporaryDirectory() as base_dir,
            tempfile.TemporaryDirectory() as cwd_dir,
        ):
            # Create MCP server in both locations with different markers
            base_server = Path(base_dir) / "server.py"
            base_server.write_text(
                """
from fastmcp import FastMCP

mcp = FastMCP("BaseDirServer")
"""
            )

            cwd_server = Path(cwd_dir) / "server.py"
            cwd_server.write_text(
                """
from fastmcp import FastMCP

mcp = FastMCP("CwdServer")
"""
            )

            orig_cwd = os.getcwd()
            try:
                os.chdir(cwd_dir)
                server = load_mcp_server("server.py", base_dir=base_dir)
                # Should load from base_dir, not cwd
                assert server is not None
                assert type(server).__name__ == "FastMCP"
                # Verify it loaded the base_dir version
                assert "BaseDirServer" in str(server)
            finally:
                os.chdir(orig_cwd)

    def test_fallback_to_cwd_when_base_dir_missing(self):
        """Test fallback to CWD when base_dir doesn't contain the file."""
        with (
            tempfile.TemporaryDirectory() as base_dir,
            tempfile.TemporaryDirectory() as cwd_dir,
        ):
            # Create MCP server only in CWD
            cwd_server = Path(cwd_dir) / "server.py"
            cwd_server.write_text(
                """
from fastmcp import FastMCP

mcp = FastMCP("CwdServer")
"""
            )

            orig_cwd = os.getcwd()
            try:
                os.chdir(cwd_dir)
                server = load_mcp_server("server.py", base_dir=base_dir)
                # Should load from CWD as fallback
                assert server is not None
                assert type(server).__name__ == "FastMCP"
                assert "CwdServer" in str(server)
            finally:
                os.chdir(orig_cwd)

    def test_fallback_to_sys_path(self):
        """Test fallback to sys.path when neither base_dir nor CWD work."""
        import tempfile

        # Create a temporary directory and add it to sys.path
        with tempfile.TemporaryDirectory() as sys_path_dir:
            # Create MCP server in sys.path location
            sys_path_server = Path(sys_path_dir) / "server.py"
            sys_path_server.write_text(
                """
from fastmcp import FastMCP

mcp = FastMCP("SysPathServer")
"""
            )

            # Temporarily add to sys.path
            original_sys_path = sys.path.copy()
            sys.path.insert(0, sys_path_dir)

            try:
                # Try to load from a non-existent location
                server = load_mcp_server(
                    "server.py", base_dir="/nonexistent", force_reload=True
                )
                # Should find it in sys.path
                assert server is not None
                assert type(server).__name__ == "FastMCP"
                assert "SysPathServer" in str(server)
            finally:
                # Restore sys.path
                sys.path[:] = original_sys_path

    def test_enhanced_error_message_shows_all_locations(self):
        """Test error message shows all search locations."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_mcp_server("nonexistent.py", base_dir="/some/base/dir")

        error_msg = str(exc_info.value)
        assert "MCP server file not found: nonexistent.py" in error_msg
        assert "Searched in:" in error_msg
        assert "playbook directory" in error_msg
        assert "current working directory" in error_msg
        assert "Python path" in error_msg

    def test_absolute_path_bypasses_search_strategy(self):
        """Test that absolute paths bypass the search strategy."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(
                """
from fastmcp import FastMCP

mcp = FastMCP("AbsoluteServer")
"""
            )
            tmp_path = tmp.name

        try:
            # Load using absolute path
            server = load_mcp_server(tmp_path)
            assert server is not None
            assert type(server).__name__ == "FastMCP"
            assert "AbsoluteServer" in str(server)
        finally:
            os.unlink(tmp_path)
