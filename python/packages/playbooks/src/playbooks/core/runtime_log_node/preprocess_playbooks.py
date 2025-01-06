"""Preprocess playbooks runtime log node."""

from typing import Dict, Optional

from .base import RuntimeLogNode


class PreprocessPlaybooksRuntimeLogNode(RuntimeLogNode):
    """A log node for preprocessing playbooks."""

    @classmethod
    def create(
        cls,
        playbooks: str,
        metadata: Optional[Dict] = None,
        parent_log_node_id: Optional[int] = None,
    ) -> "PreprocessPlaybooksRuntimeLogNode":
        instance = cls(
            parent_log_node_id=parent_log_node_id,
            type="preprocess_playbooks",
            info={
                "playbooks": playbooks,
                "metadata": metadata or {},
            },
        )
        return instance
