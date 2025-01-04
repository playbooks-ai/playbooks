"""State management for playbooks runtime."""

import base64
import json
import os
import pickle
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from playbooks.core.runtime import PlaybooksRuntime


@dataclass
class SessionState:
    """Represents a session state that can be persisted."""

    session_id: str
    runtime_data: Optional[str] = None  # Base64 encoded pickle of runtime
    last_activity: datetime = datetime.utcnow()

    @property
    def is_valid(self) -> bool:
        """Check if the session is still valid (not expired)."""
        return (datetime.utcnow() - self.last_activity) < timedelta(hours=24)

    def update_activity(self):
        """Update the last activity timestamp."""
        self.last_activity = datetime.utcnow()


class StateManager:
    """Manages persistence of playbooks runtime state."""

    def __init__(self, state_dir: Optional[str] = None):
        """Initialize the state manager.

        Args:
            state_dir: Directory to store state files. Defaults to ~/.playbooks/state
        """
        if state_dir is None:
            state_dir = os.path.expanduser("~/.playbooks/state")
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _get_state_path(self, session_id: str) -> Path:
        """Get the path to the state file for a session."""
        return self.state_dir / f"{session_id}.json"

    def save_state(self, session_id: str, runtime: PlaybooksRuntime) -> None:
        """Save runtime state to disk.

        Args:
            session_id: The session ID to save state for
            runtime: The runtime object to save
        """
        # Serialize runtime
        runtime_data = base64.b64encode(pickle.dumps(runtime)).decode("utf-8")

        # Create or update session state
        state = SessionState(
            session_id=session_id,
            runtime_data=runtime_data,
            last_activity=datetime.utcnow(),
        )

        # Save to file
        state_path = self._get_state_path(session_id)
        with open(state_path, "w") as f:
            json.dump(
                {
                    "session_id": state.session_id,
                    "runtime_data": state.runtime_data,
                    "last_activity": state.last_activity.isoformat(),
                },
                f,
            )

    def load_state(self, session_id: str) -> Optional[PlaybooksRuntime]:
        """Load runtime state from disk.

        Args:
            session_id: The session ID to load state for

        Returns:
            The runtime object if found and valid, None otherwise
        """
        state_path = self._get_state_path(session_id)
        if not state_path.exists():
            return None

        try:
            # Load state from file
            with open(state_path) as f:
                data = json.load(f)

            # Create session state
            state = SessionState(
                session_id=data["session_id"],
                runtime_data=data["runtime_data"],
                last_activity=datetime.fromisoformat(data["last_activity"]),
            )

            # Check if session is valid
            if not state.is_valid:
                return None

            # Deserialize runtime
            runtime_data = base64.b64decode(state.runtime_data.encode("utf-8"))
            runtime = pickle.loads(runtime_data)

            return runtime
        except Exception as e:
            print(f"Error loading state: {e}")
            return None

    def clear_state(self, session_id: str) -> None:
        """Clear the state for a session.

        Args:
            session_id: The session ID to clear state for
        """
        state_path = self._get_state_path(session_id)
        if state_path.exists():
            state_path.unlink()
