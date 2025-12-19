"""Remote AI agent implementation for external LLM services.

This module provides agents that communicate with remote LLM services
for playbook execution and processing.
"""

import logging
from typing import Any, Dict

from playbooks.infrastructure.event_bus import EventBus

from .ai_agent import AIAgent

logger = logging.getLogger(__name__)


class RemoteAIAgent(AIAgent):
    """
    Abstract base class for remote AI agents.

    Remote agents communicate with external services to provide playbooks/tools.
    This class provides common functionality for all remote agent types.
    """

    def __init__(
        self,
        event_bus: EventBus,
        remote_config: Dict[str, Any],
        source_line_number: int = None,
        agent_id: str = None,
        **kwargs,
    ):
        """Initialize a remote AI agent.

        Args:
            klass: The class/type of this agent.
            description: Human-readable description of the agent.
            event_bus: The event bus for publishing events.
            remote_config: Configuration for the remote connection.
            source_line_number: The line number in the source markdown where this
                agent is defined.
            agent_id: Optional agent ID. If not provided, will generate UUID.
        """
        super().__init__(
            event_bus=event_bus,
            kwargs=kwargs,
            source_line_number=source_line_number,
            agent_id=agent_id,
            **kwargs,
        )
        self.remote_config = remote_config
        self.transport = None
        self._connected = False
        self._discovered = False

    async def connect(self) -> None:
        """Establish connection to the remote service."""
        if self._connected and self.transport and self.transport.is_connected:
            return

        try:
            if self.transport:
                await self.transport.connect()
                self._connected = self.transport.is_connected
                logger.info(f"Connected to remote agent {self.klass}")
        except Exception as e:
            logger.error(f"Failed to connect to remote agent {self.klass}: {str(e)}")
            self._connected = False
            raise

    async def disconnect(self) -> None:
        """Close connection to the remote service."""
        if not self._connected:
            return

        try:
            if self.transport:
                await self.transport.disconnect()
                logger.info(f"Disconnected from remote agent {self.klass}")
        except Exception as e:
            logger.warning(
                f"Error disconnecting from remote agent {self.klass}: {str(e)}"
            )
        finally:
            self._connected = False

    async def initialize(self):
        """Connect and discover playbooks, then execute BGN trigger playbooks."""
        if not self._connected:
            await self.connect()
        if not self._discovered:
            await self.discover_playbooks()
        await super().initialize()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
