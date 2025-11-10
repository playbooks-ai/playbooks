"""Registry for extension providers.

Manages registration and discovery of extension implementations via:
1. Direct registration (for core implementations)
2. Entry points (for external packages like playbooks-enterprise)
"""

from typing import Optional, Type
from . import CheckpointProvider


class ExtensionRegistry:
    """Global registry for extension providers."""

    _checkpoint_provider_class: Optional[Type[CheckpointProvider]] = None
    _checkpoint_provider_instance: Optional[CheckpointProvider] = None

    @classmethod
    def register_checkpoint_provider(
        cls, provider_class: Type[CheckpointProvider]
    ) -> None:
        """Register a checkpoint provider implementation.

        Args:
            provider_class: Class implementing CheckpointProvider interface
        """
        cls._checkpoint_provider_class = provider_class
        cls._checkpoint_provider_instance = None

    @classmethod
    def get_checkpoint_provider(cls, **init_kwargs) -> Optional[CheckpointProvider]:
        """Get checkpoint provider instance.

        Lazily instantiates the provider on first access.

        Args:
            **init_kwargs: Initialization arguments for provider

        Returns:
            Provider instance or None if not registered
        """
        if cls._checkpoint_provider_instance is None:
            if cls._checkpoint_provider_class is not None:
                cls._checkpoint_provider_instance = cls._checkpoint_provider_class(
                    **init_kwargs
                )
        return cls._checkpoint_provider_instance

    @classmethod
    def has_checkpoint_provider(cls) -> bool:
        """Check if a checkpoint provider is registered."""
        return cls._checkpoint_provider_class is not None

    @classmethod
    def reset(cls) -> None:
        """Reset registry (primarily for testing)."""
        cls._checkpoint_provider_class = None
        cls._checkpoint_provider_instance = None


def discover_and_register_providers() -> None:
    """Discover providers from installed packages via entry points.

    External packages can register providers by defining entry points:

    [tool.poetry.plugins."playbooks.extensions"]
    checkpoint_provider = "package.module:ProviderClass"
    """
    try:
        from importlib.metadata import entry_points

        eps = entry_points()
        if hasattr(eps, "select"):
            playbook_extensions = eps.select(group="playbooks.extensions")
        else:
            playbook_extensions = eps.get("playbooks.extensions", [])

        for ep in playbook_extensions:
            if ep.name == "checkpoint_provider":
                provider_class = ep.load()
                ExtensionRegistry.register_checkpoint_provider(provider_class)
    except Exception:
        pass


discover_and_register_providers()
