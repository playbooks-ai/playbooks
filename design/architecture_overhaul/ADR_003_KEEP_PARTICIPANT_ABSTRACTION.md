# ADR 003: Keep Participant Abstraction

**Date**: November 2, 2025  
**Status**: Accepted  
**Phase**: Phase 3

## Context

The architecture critique (section 2.2) suggested the Participant abstraction might be over-engineered since AgentParticipant and HumanParticipant had nearly identical implementations (both just call `agent._add_message_to_buffer()`).

## Problem Considered

Was the Participant abstraction necessary, or could we simplify by having Channel work directly with agents?

### Arguments for Removal
- Both implementations are similar (just call agent method)
- Only 2 participant types currently exist
- Adds ~150 lines of code
- Extra indirection layer

### Arguments for Keeping
- **Future extensibility**: Enable remote agents, network communication
- **Clean separation**: Channel routing separate from delivery mechanisms
- **Minimal overhead**: ~150 lines, no performance impact
- **Future-proofing**: Planned distributed agent architecture

## Decision

**Keep the Participant abstraction** for future extensibility.

The abstraction provides a clean extension point for:

1. **RemoteParticipant**: Network-connected agents (WebSocket, gRPC)
2. **DatabaseParticipant**: Message logging to persistent storage
3. **WebhookParticipant**: Forward messages to external systems
4. **QueueParticipant**: Integration with message queues (Redis, RabbitMQ)

## Consequences

### Positive
- ✅ **Extensibility**: Easy to add new participant types without changing Channel
- ✅ **Clean architecture**: Clear boundary between routing and delivery
- ✅ **Open/Closed Principle**: Open for extension, closed for modification
- ✅ **Future-ready**: Supports planned distributed architecture

### Negative
- ⚠️ **Slight complexity**: Extra abstraction layer to understand
- ⚠️ **Current similarity**: AgentParticipant and HumanParticipant are similar now

### Mitigations
- **Comprehensive documentation**: Added rationale and examples to participant.py
- **Examples provided**: Documented future use cases (Remote, Database, Webhook)
- **Minimal overhead**: Only ~150 lines, negligible performance impact

## Alternatives Considered

### Alternative 1: Remove Participant, use agents directly
```python
class Channel:
    def __init__(self, channel_id: str, agents: List[BaseAgent]):
        self.agents = agents
```

**Rejected because**: 
- Hard to extend for network participants
- Couples Channel to BaseAgent
- Would need refactoring when distributed agents are added

### Alternative 2: Use Protocol instead of ABC
```python
class Participant(Protocol):
    id: str
    klass: str
    async def deliver(self, message: Message) -> None: ...
```

**Considered but not needed**: ABC is fine, provides runtime checking

## Implementation

- **Phase 3**: Documented rationale in `participant.py`
- **Examples added**: RemoteParticipant, DatabaseParticipant, WebhookParticipant
- **Design principles**: Interface segregation, open/closed, dependency inversion

## References

- ARCHITECTURE_CRITIQUE.md section 2.2 - Participant abstraction analysis
- src/playbooks/channels/participant.py - Implementation and documentation

