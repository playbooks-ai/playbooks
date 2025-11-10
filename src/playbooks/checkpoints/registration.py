"""Auto-registration of filesystem checkpoint provider."""

from playbooks.config import config
from playbooks.extensions.registry import ExtensionRegistry
from .filesystem import FilesystemCheckpointProvider


def register_filesystem_provider():
    """Register filesystem checkpoint provider if durability is enabled."""
    if config.durability.enabled and config.durability.storage_type == "filesystem":
        ExtensionRegistry.register_checkpoint_provider(FilesystemCheckpointProvider)


register_filesystem_provider()
