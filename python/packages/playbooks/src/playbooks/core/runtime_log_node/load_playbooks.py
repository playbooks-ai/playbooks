"""Load playbooks runtime log node."""

from datetime import datetime
from typing import List, Optional

from .base import RuntimeLogNode


class LoadPlaybooksRuntimeLogNode(RuntimeLogNode):
    """A log node for loading playbooks."""

    @classmethod
    def create(
        cls,
        playbook_paths: List[str],
        playbooks: str,
        parent_log_node_id: Optional[int] = None,
    ) -> "LoadPlaybooksRuntimeLogNode":
        instance = cls(
            parent_log_node_id=parent_log_node_id,
            type="load_playbooks",
            info={
                "playbook_paths": playbook_paths,
            },
        )
        instance.set_playbooks(playbooks)
        return instance

    def set_playbooks(self, playbooks: str):
        """Set playbooks content in the log node's info field."""
        self.info["playbooks"] = playbooks
        self.updated_at = datetime.fromisoformat("2025-01-04T23:25:56-08:00")
