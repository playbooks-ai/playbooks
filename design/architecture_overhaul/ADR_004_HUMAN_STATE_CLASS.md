# ADR 004: Separate HumanState Class

**Date**: November 2, 2025  
**Status**: Accepted  
**Phase**: Phase 3A

## Context

HumanAgent originally used the same ExecutionState class as AI agents. ExecutionState includes call stacks, variables, session logs, and execution tracking - all designed for agents that execute LLM-based playbooks.

## Problem

HumanAgent doesn't execute playbooks, so it doesn't need:
- **CallStack**: Humans don't have instruction pointers or execution frames
- **Variables**: Humans don't have execution variables ($-prefixed state)
- **SessionLog**: Humans don't have LLM execution history
- **owned_meetings**: Humans don't own/create meetings

Using ExecutionState for HumanAgent was:
- **Wasteful**: Allocated unused data structures
- **Confusing**: Suggested humans could execute playbooks
- **Misleading**: TODO comment acknowledged this was wrong

## Decision

Create **HumanState** - a minimal state class specifically for human agents:

```python
class HumanState:
    """Minimal state for human agents."""
    
    def __init__(self, event_bus: EventBus, klass: str, agent_id: str):
        self.event_bus = event_bus
        self.klass = klass
        self.agent_id = agent_id
        self.joined_meetings: Dict[str, JoinedMeeting] = {}
    
    def get_current_meeting(self) -> Optional[str]:
        # Return current meeting if in one
```

**What HumanState has**:
- ✅ `joined_meetings`: Track which meetings human has joined
- ✅ `get_current_meeting()`: Required for meeting context resolution
- ✅ Basic identification (klass, agent_id)

**What HumanState doesn't have**:
- ❌ CallStack (no playbook execution)
- ❌ Variables (no execution state)
- ❌ SessionLog (no LLM history)
- ❌ owned_meetings (humans don't create meetings)

## Consequences

### Positive
- ✅ **Memory efficiency**: ~90% reduction in state overhead for humans
- ✅ **Clarity**: Type makes it obvious humans don't execute playbooks
- ✅ **Correctness**: Matches actual behavior
- ✅ **Maintainability**: Simpler interface, less confusion

### Negative
- ⚠️ **Interface divergence**: HumanState vs ExecutionState have different APIs
- ⚠️ **Duck typing needed**: Code checks for `hasattr(state, 'call_stack')`

### Mitigations
- **Common interface**: Both have `get_current_meeting()` for meeting resolution
- **Clear documentation**: HumanState docstring explains minimal nature
- **Comprehensive tests**: 12 tests verify HumanState behavior

## Alternatives Considered

### Alternative 1: Empty ExecutionState
Keep ExecutionState but don't populate call_stack, variables, etc.

**Rejected because**:
- Still allocates unnecessary objects
- Confusing (why have empty structures?)
- Doesn't clearly communicate intent

### Alternative 2: Shared StateProtocol
Create protocol/interface both implement.

**Rejected because**:
- Over-engineering for current needs
- States are fundamentally different
- Duck typing works fine for the few checks needed

## Implementation

- **Created**: `src/playbooks/human_state.py` (58 lines)
- **Updated**: `src/playbooks/agents/human_agent.py` to use HumanState
- **Tests**: `tests/unit/test_human_state.py` (12 tests, 100% coverage)
- **Removed**: TODO comment acknowledging this issue

## Future Considerations

When multi-human support is added (Phase 4):
- HumanState may need delivery preferences
- May need message buffer configuration
- Interface should remain minimal and focused

## References

- src/playbooks/human_state.py - Implementation
- tests/unit/test_human_state.py - Tests
- src/playbooks/agents/human_agent.py line 23 - Original TODO

