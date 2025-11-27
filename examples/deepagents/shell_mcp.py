"""
Shell MCP Server for DeepAgent Playbooks
Provides shell command execution capabilities
"""

import os
import subprocess
from typing import Dict, Any, Optional

from fastmcp import FastMCP

mcp = FastMCP("Shell Tools")


@mcp.tool
def shell(
    command: str, working_dir: Optional[str] = None, timeout: int = 300
) -> Dict[str, Any]:
    """Execute a shell command and return the output.

    IMPORTANT: This tool executes commands on the host system. Use with caution.

    Args:
        command: The shell command to execute
        working_dir: Working directory for command execution (default: current directory)
        timeout: Command timeout in seconds (default: 300)

    Returns:
        Dictionary with command output, return code, and execution details
    """
    try:
        # Determine working directory
        cwd = os.path.abspath(working_dir) if working_dir else os.getcwd()

        # Execute command
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "command": command,
            "working_dir": cwd,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Command timed out after {timeout} seconds",
            "command": command,
            "working_dir": cwd if "cwd" in locals() else None,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error executing command: {str(e)}",
            "command": command,
            "working_dir": cwd if "cwd" in locals() else None,
        }


@mcp.tool
def get_cwd() -> Dict[str, Any]:
    """Get the current working directory.

    Returns:
        Dictionary with the current working directory path
    """
    try:
        return {"success": True, "cwd": os.getcwd()}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
