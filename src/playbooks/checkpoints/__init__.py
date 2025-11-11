"""Checkpoint system for durable execution.

Provides baseline filesystem-based checkpointing suitable for development
and single-node deployments. Enterprise implementations can provide scalable
alternatives with PostgreSQL, Redis, or distributed storage.
"""

from .filesystem import FilesystemCheckpointProvider
from .manager import CheckpointManager
from .recovery import RecoveryCoordinator
from .program_coordinator import ProgramCheckpointCoordinator
from .session_manager import SessionManager

from playbooks.extensions.registry import ExtensionRegistry

ExtensionRegistry.register_checkpoint_provider(FilesystemCheckpointProvider)

__all__ = [
    "FilesystemCheckpointProvider",
    "CheckpointManager",
    "RecoveryCoordinator",
    "ProgramCheckpointCoordinator",
    "SessionManager",
]
