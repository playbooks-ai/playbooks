# ADR 001: Structured ID Types

**Date**: November 2, 2025  
**Status**: Accepted  
**Phase**: Phase 2

## Context

The Playbooks framework used string-based identifiers with multiple ambiguous formats for agent and meeting identification. Code converted between specs ("agent 1234") and IDs ("1234") constantly, with 40+ conversion sites and 250+ lines of code dedicated to format handling.

## Problem

- **Stringly-typed**: Everything was `str`, no type safety
- **Ambiguous formats**: "112" could be agent or meeting ID
- **Performance waste**: 50-70% of routing time spent parsing strings
- **Bug-prone**: Easy to mix formats and compare incompatible strings
- **Maintenance burden**: Conversion logic scattered across 9 files

## Decision

Implement **structured identifier types** using frozen dataclasses:

```python
@dataclass(frozen=True)
class AgentID:
    id: str
    
    @classmethod
    def parse(cls, spec_or_id: str) -> "AgentID":
        # Parse once at boundary
        
    def __str__(self) -> str:
        return f"agent {self.id}"  # Spec format for LLMs
```

**Pattern**: Parse once at API boundaries, use structured types internally.

## Consequences

### Positive
- ✅ **50% code reduction** in ID handling (250 → 125 lines)
- ✅ **75% fewer conversion sites** (40+ → ~10)
- ✅ **Type safety**: Compiler catches ID/spec mixing
- ✅ **Performance**: Parse once instead of 4+ times per message
- ✅ **Clarity**: `AgentID` vs `MeetingID` is explicit

### Negative
- ⚠️ **Learning curve**: New developers need to understand the pattern
- ⚠️ **Migration effort**: 3 weeks to fully implement

### Mitigations
- Comprehensive documentation
- Helper methods (`.parse()`, `__str__()`) make usage simple
- Clear error messages for invalid formats

## Implementation

- **Phase 2**: Created `identifiers.py` with AgentID, MeetingID, EntityID
- **Migration**: Updated Message, Program, Channel to use structured types
- **Cleanup**: Deprecated SpecUtils, removed conversion logic

## References

- ARCHITECTURE_CRITIQUE_IDSPEC.md - Full analysis
- ARCHITECTURE_IMPLEMENTATION_PLAN.md - Phase 2 details

