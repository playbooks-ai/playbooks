"""
Debug session management for Playbooks.

This module manages debug sessions following the debugpy pattern.
"""

import threading
from typing import Dict, Set

from ..common import log

# Global session tracking
_sessions: Dict[str, "DebugSession"] = {}
_sessions_lock = threading.Lock()
_all_sessions_ended = threading.Event()


class DebugSession:
    """Represents a debug session for a playbook."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.is_ended = False

        with _sessions_lock:
            _sessions[session_id] = self

    def end(self):
        """End this debug session."""
        if self.is_ended:
            return

        self.is_ended = True
        log.info(f"Debug session {self.session_id} ended")

        with _sessions_lock:
            if self.session_id in _sessions:
                del _sessions[self.session_id]

            # Check if all sessions have ended
            if not _sessions:
                _all_sessions_ended.set()


def create_session(session_id: str) -> DebugSession:
    """Create a new debug session."""
    log.info(f"Creating debug session: {session_id}")
    return DebugSession(session_id)


def get_session(session_id: str) -> DebugSession:
    """Get an existing debug session."""
    with _sessions_lock:
        return _sessions.get(session_id)


def end_session(session_id: str):
    """End a debug session."""
    session = get_session(session_id)
    if session:
        session.end()


def wait_until_ended():
    """Wait until all debug sessions have ended."""
    _all_sessions_ended.wait()


def get_active_sessions() -> Set[str]:
    """Get the set of active session IDs."""
    with _sessions_lock:
        return set(_sessions.keys())
