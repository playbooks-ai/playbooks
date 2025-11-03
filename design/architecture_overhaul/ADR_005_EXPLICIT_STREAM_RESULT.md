# ADR 005: Explicit StreamResult Type

**Date**: November 2, 2025  
**Status**: Accepted  
**Phase**: Phase 1

## Context

The `Program.start_stream()` method returned `Optional[str]` where `None` had special meaning:
- `None` = "skip streaming" (agent-to-agent communication)
- `stream_id` = streaming was started (human recipient)

This created confusing control flow where callers had to check `if stream_id is None` to determine what happened.

## Problem

**Overloaded return value semantics**:
```python
stream_id = await start_stream(...)

if stream_id is None:
    # Did streaming fail? Or was it intentionally skipped?
    # Unclear without reading implementation
```

**Issues**:
- `None` means "skip streaming" not "error"
- Violates principle of least surprise
- Hard to distinguish skip from failure
- Confusing for error handling

## Decision

Use **explicit result type** with clear semantics:

```python
@dataclass(frozen=True)
class StreamResult:
    stream_id: Optional[str]
    should_stream: bool
    
    @classmethod
    def start(cls, stream_id: str) -> "StreamResult":
        return cls(stream_id=stream_id, should_stream=True)
    
    @classmethod
    def skip(cls) -> "StreamResult":
        return cls(stream_id=None, should_stream=False)
```

**Usage**:
```python
result = await start_stream(...)

if result.should_stream:
    # Streaming was started
    await stream_chunk(result.stream_id, ...)
else:
    # Streaming was skipped (agent-to-agent)
    await send_direct(...)
```

## Consequences

### Positive
- ✅ **Explicit intent**: `should_stream` boolean is clear
- ✅ **Self-documenting**: Code reads naturally
- ✅ **Type-safe**: Can't forget to check
- ✅ **Extensible**: Can add more fields (error, reason, etc.)

### Negative
- ⚠️ **More code**: Requires dataclass definition (~30 lines)
- ⚠️ **Breaking change**: Callers must update from `if stream_id is None`

### Mitigations
- Helper methods (`.start()`, `.skip()`) make creation simple
- Clear migration path (replace None check with `should_stream` check)
- Better code clarity outweighs minor verbosity

## Alternatives Considered

### Alternative 1: Use tuple (stream_id, should_stream)
```python
stream_id, should_stream = await start_stream(...)
```

**Rejected because**:
- Less explicit than named type
- Easy to mix up order
- No helper methods

### Alternative 2: Use enum StreamAction
```python
class StreamAction(Enum):
    STARTED = "started"
    SKIPPED = "skipped"

return (StreamAction.STARTED, stream_id) or (StreamAction.SKIPPED, None)
```

**Rejected because**:
- More complex than dataclass
- Still using tuple pattern
- Enum doesn't add value here

## Implementation

- **Created**: `src/playbooks/stream_result.py` (30 lines)
- **Updated**: `Program.start_stream()` returns StreamResult
- **Updated**: `BaseAgent._say_with_streaming()` uses `result.should_stream`
- **Tests**: Covered by existing integration tests (83% coverage)

## Future Considerations

StreamResult could be extended with:
- `error: Optional[str]` - Error message if streaming failed
- `reason: str` - Why streaming was skipped
- `metadata: Dict` - Additional context

## References

- ARCHITECTURE_CRITIQUE.md section 1.4 - Stream ID return confusion
- src/playbooks/stream_result.py - Implementation

