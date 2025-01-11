"""Base runtime log node class."""

import uuid
from datetime import datetime
from typing import Dict, Optional


class RuntimeLogNode:
    """A log node that can be serialized to JSON."""

    def __init__(
        self,
        parent_log_node_id: Optional[int] = None,
        type: str = None,
        info: Optional[Dict] = None,
    ):
        self.id = uuid.uuid4()
        self.parent_log_node_id = parent_log_node_id
        self.type = type
        self.info = info or {}
        self.created_at = datetime.fromisoformat("2025-01-04T23:29:24-08:00")
        self.updated_at = datetime.fromisoformat("2025-01-04T23:29:24-08:00")

    def set_error(self, error: str):
        """Set error information in the log node's info field."""
        self.info["error"] = error
        self.updated_at = datetime.fromisoformat("2025-01-04T23:29:24-08:00")
