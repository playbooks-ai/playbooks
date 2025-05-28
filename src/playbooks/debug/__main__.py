"""
Debug adapter entry point for Playbooks.

This module provides the main entry point for the Playbooks debug adapter,
following the Debug Adapter Protocol (DAP) specification and debugpy pattern.

Usage:
    python -m playbooks.debug --listen <port> [options]
    python -m playbooks.debug --connect <host>:<port> [options]
"""

from .adapter import main

if __name__ == "__main__":
    main()
