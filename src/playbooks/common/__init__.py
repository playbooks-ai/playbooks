"""
Common utilities for Playbooks debugging.

This module provides shared utilities used across the debugging infrastructure,
following the pattern established by debugpy.
"""

from . import log, sockets

__all__ = ["log", "sockets"]
