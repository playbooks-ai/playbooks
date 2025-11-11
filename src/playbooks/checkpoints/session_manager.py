"""Session management for checkpoint resume.

Tracks the last session ID for each playbook execution to enable resume.
"""

import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages session IDs for playbook executions to enable resume."""

    def __init__(self, storage_path: str = ".checkpoints"):
        """Initialize session manager.

        Args:
            storage_path: Base path for checkpoint storage
        """
        self.storage_path = Path(storage_path)
        self.session_file = self.storage_path / ".sessions.json"
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _get_execution_key(self, program_paths: List[str]) -> str:
        """Generate a stable key for a playbook execution.

        Uses hash of sorted absolute paths to create a consistent identifier.

        Args:
            program_paths: List of playbook file paths

        Returns:
            Hex string hash of the playbook paths
        """
        # Sort paths and convert to absolute for consistency
        abs_paths = sorted([str(Path(p).resolve()) for p in program_paths])
        paths_str = "|".join(abs_paths)
        return hashlib.sha256(paths_str.encode()).hexdigest()[:16]

    async def get_last_session(self, program_paths: List[str]) -> Optional[str]:
        """Get the last session ID for a playbook execution.

        Args:
            program_paths: List of playbook file paths

        Returns:
            Session ID if found, None otherwise
        """
        execution_key = self._get_execution_key(program_paths)

        if not await asyncio.to_thread(self.session_file.exists):
            return None

        try:
            data = await asyncio.to_thread(self.session_file.read_text)
            sessions = json.loads(data)
            return sessions.get(execution_key)
        except Exception as e:
            logger.warning(f"Failed to read session file: {e}")
            return None

    async def save_session(self, program_paths: List[str], session_id: str) -> None:
        """Save the current session ID for a playbook execution.

        Args:
            program_paths: List of playbook file paths
            session_id: Session ID to save
        """
        execution_key = self._get_execution_key(program_paths)

        # Load existing sessions
        sessions = {}
        if await asyncio.to_thread(self.session_file.exists):
            try:
                data = await asyncio.to_thread(self.session_file.read_text)
                sessions = json.loads(data)
            except Exception as e:
                logger.warning(f"Failed to read existing sessions: {e}")

        # Update with new session
        sessions[execution_key] = session_id

        # Save back
        try:
            data = json.dumps(sessions, indent=2)
            await asyncio.to_thread(self.session_file.write_text, data)
            logger.debug(
                f"Saved session {session_id} for execution key {execution_key}"
            )
        except Exception as e:
            logger.error(f"Failed to save session file: {e}")

    async def clear_session(self, program_paths: List[str]) -> None:
        """Clear the saved session for a playbook execution.

        Args:
            program_paths: List of playbook file paths
        """
        execution_key = self._get_execution_key(program_paths)

        if not await asyncio.to_thread(self.session_file.exists):
            return

        try:
            data = await asyncio.to_thread(self.session_file.read_text)
            sessions = json.loads(data)

            if execution_key in sessions:
                del sessions[execution_key]
                data = json.dumps(sessions, indent=2)
                await asyncio.to_thread(self.session_file.write_text, data)
                logger.debug(f"Cleared session for execution key {execution_key}")
        except Exception as e:
            logger.warning(f"Failed to clear session: {e}")
