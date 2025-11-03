"""Channel-based communication system for playbooks.

This module provides a unified channel architecture for all communication types:
- Direct messages (agent-to-agent, agent-to-human)
- Conversations (2 participants)
- Meetings (N participants)

Key components:
- Channel: Universal communication channel
- Participant: Interface for channel participants (agents, humans, etc.)
- Stream events: Support for streaming communication
"""

from .channel import Channel, StreamObserver
from .participant import AgentParticipant, HumanParticipant, Participant
from .stream_events import StreamChunkEvent, StreamCompleteEvent, StreamStartEvent

__all__ = [
    "Channel",
    "Participant",
    "AgentParticipant",
    "HumanParticipant",
    "StreamObserver",
    "StreamStartEvent",
    "StreamChunkEvent",
    "StreamCompleteEvent",
]
