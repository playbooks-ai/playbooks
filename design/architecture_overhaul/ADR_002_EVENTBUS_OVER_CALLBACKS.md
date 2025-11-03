# ADR 002: EventBus Over Custom Callbacks

**Date**: November 2, 2025  
**Status**: Accepted  
**Phase**: Phase 3

## Context

The Program class maintained custom callback lists for channel creation events:
```python
self._channel_creation_callbacks: List[Callable[[Channel], Awaitable[None]]] = []
```

Meanwhile, the framework already had a robust EventBus implementation for event handling.

## Problem

- **Duplication**: Two event systems (EventBus + custom callbacks)
- **Inconsistency**: Channel events used callbacks, other events used EventBus
- **No error isolation**: One bad callback crashed channel creation
- **Hard to manage**: Manual list management, no unregister mechanism
- **Callback hell**: Difficult to track registration/invocation order

## Decision

**Remove custom callbacks and use EventBus for all events**, including channel creation.

```python
# Before (custom callbacks)
program.register_channel_creation_callback(my_callback)

# After (EventBus)
@dataclass
class ChannelCreatedEvent:
    channel_id: str
    channel: Channel

program.event_bus.subscribe(ChannelCreatedEvent, my_handler)
```

## Consequences

### Positive
- ✅ **Unified event system**: All events use EventBus
- ✅ **Better error handling**: EventBus has built-in error isolation
- ✅ **Easier to manage**: Standard subscribe/unsubscribe patterns
- ✅ **Better testability**: Can verify events were published
- ✅ **Consistent API**: Developers learn one pattern

### Negative
- ⚠️ **Breaking change**: Applications using callbacks must migrate

### Mitigations
- EventBus was already available, no new dependencies
- Migration is straightforward (1:1 mapping)
- Better pattern going forward

## Implementation

- **Phase 3**: Created `ChannelCreatedEvent`
- **Removed**: `_channel_creation_callbacks` list and registration methods
- **Updated**: `streaming_observer.py`, `agent_chat.py`, `web_server.py` to use EventBus

## References

- ARCHITECTURE_CRITIQUE.md section 2.1 - Channel callback anti-pattern analysis
- src/playbooks/events.py - ChannelCreatedEvent implementation

