"""
Playbooks Debug Module.

This module provides debugging capabilities for Playbooks programs,
implementing the Debug Adapter Protocol (DAP) for integration with
VS Code and other editors.

Main components:
- PlaybookDebugAdapter: Main debug adapter implementing DAP
- DebugServer: Internal debug server for communication with playbook execution
- DAPHandler: Handles DAP message processing
- ProcessManager: Manages target process lifecycle
"""

from .adapter import PlaybookDebugAdapter
from .dap_handler import DAPHandler
from .process_manager import ProcessManager
from .server import DebugServer

__all__ = [
    "PlaybookDebugAdapter",
    "DAPHandler",
    "ProcessManager",
    "DebugServer",
]
