# LLM Context Compaction - Product Requirements Document (PRD)

## Executive Summary

This document outlines the design and implementation of an LLM context compaction strategy for the Playbooks framework. The goal is to manage growing context size from accumulated UserInputLLMMessage and AssistantResponseLLMMessage pairs while preserving recent interactions and optimizing for LLM context caching.

## Problem Statement

### Current Issue
As playbook programs execute, various LLMMessages accumulate in the call stack, primarily:
- **UserInputLLMMessage**: User instructions and inputs
- **AssistantResponseLLMMessage**: LLM responses and outputs

This leads to:
1. **Context Size Growth**: Unbounded accumulation of message pairs
2. **Performance Degradation**: Increased LLM API costs and latency
3. **Memory Pressure**: Growing memory usage for long-running sessions
4. **Cache Inefficiency**: Suboptimal use of LLM context caching

### Root Cause Analysis
- **Location**: `self.execution_state.call_stack.get_llm_messages()` in `interpreter_prompt.py:158`
- **Growth Pattern**: Linear accumulation of user/assistant message pairs
- **No Compaction**: Currently no strategy to reduce historical context
- **Cache Suboptimal**: No consideration for LLM context caching behavior

## Core Design Principles

1. **Minimal Disruption**: Preserve existing API and message handling patterns
2. **Context Caching Aware**: Respect LLM context caching with prefix-based optimization
3. **Progressive Strategy**: Batch compaction rather than individual message processing
4. **Configuration Driven**: Tunable parameters without code changes
5. **Preserve Recency**: Always maintain recent interaction history
6. **Clean Architecture**: Single responsibility with clear separation of concerns

## Architecture Overview

### System Integration

```
┌─────────────────────────────────────────────────────────────┐
│                  InterpreterPrompt                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  messages.extend(call_stack.get_llm_messages())     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     CallStack                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  def get_llm_messages(self) -> List[Dict[str, str]]: │   │
│  │      messages = []                                   │   │
│  │      for frame in self.frames:                       │   │
│  │          messages.extend(frame.get_llm_messages())   │   │
│  │      return messages                                 │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                LLMContextCompactor                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  - Progressive batch compaction                     │   │
│  │  - User input skipping (configurable)               │   │
│  │  - Assistant response summarization                 │   │
│  │  - Context caching optimization                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Compaction Strategy

#### Backwards Walking Logic
```
1. Walk backwards from last message
2. Count AssistantResponseLLMMessage instances
3. Mark last N (min_preserved_pairs) as FULL
4. When we have enough to trigger compaction:
   - Mark older assistant messages as COMPACT
   - Mark ALL earlier user messages as COMPACT (once compaction starts)

Example with min_preserved_pairs=3, batch_size=4:
Messages: [U1, A1, U2, A2, U3, A3, U4, A4, U5, A5, U6, A6, U7, A7]
                                       ↑         ↑         ↑
                                    FULL      FULL      FULL
         ↑compacted↑  ↑compacted↑  ↑compacted↑
```

#### Message Processing Rules (Polymorphic Design)
Each LLMMessage subclass implements its own `to_compact_message()` method:

1. **UserInputLLMMessage**: 
   - Returns `None` (complete removal during compaction)
   
2. **AssistantResponseLLMMessage**:
   - Finds first line that begins with "recap -"
   - Returns that line as compacted content
   - Directly outputs LLM API format

## Detailed Design

### Core Components

#### 1. CompactionConfig
```python
@dataclass
class CompactionConfig:
    """Configuration for LLM context compaction."""
    
    # Core strategy parameters
    min_preserved_assistant_messages: int = 3  # Always keep last N assistant messages
    batch_size: int = 4                        # Compact in batches of N
    
    # Feature toggles
    enabled: bool = True                # Master enable/disable    
```

#### LLMMessage Interface Extension
```python
class LLMMessage:
    def to_compact_message(self) -> Optional[Dict[str, str]]:
        """Return compacted message dict for LLM API or None to remove completely."""
        return self.to_full_message()  # Default: no compaction
        
class UserInputLLMMessage(LLMMessage):
    def to_compact_message(self) -> Optional[Dict[str, str]]:
        """Remove user inputs during compaction."""
        return None
        
class AssistantResponseLLMMessage(LLMMessage):
    def to_compact_message(self) -> Optional[Dict[str, str]]:
        """Use first line that begins with 'recap -' for compaction."""
        lines = self.content.split('\n')

        # find line that begins with 'recap -'
        recap_line = next((line for line in lines if line.strip().startswith('recap -')), None)
        if recap_line:
            return {
                "role": self.role.value,
                "content": recap_line
            }
        return self.content

#### 2. LLMContextCompactor
```python
class LLMContextCompactor:
    """Handles progressive compaction of LLM messages."""
    
    def __init__(self, config: Optional[CompactionConfig] = None):
        self.config = config or CompactionConfig()
        
    def compact_messages(self, messages: List[LLMMessage]) -> List[Dict[str, str]]:
        """Main entry point for message compaction - returns LLM API format."""
        if not self.config.enabled or len(messages) == 0:
            return [msg.to_full_message() for msg in messages]
            
        # Walk backwards to find AssistantResponseLLMMessage instances
        assistant_indices = []
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], AssistantResponseLLMMessage):
                assistant_indices.append(i)
                
        # Check if we have enough assistant messages to trigger compaction
        compaction_threshold = self.config.min_preserved_pairs + self.config.batch_size
        if len(assistant_indices) < compaction_threshold:
            return [msg.to_full_message() for msg in messages]
            
        # Determine compaction boundary
        # Keep last min_preserved_pairs assistant messages as FULL
        # Compact earlier ones in batch_size increments
        assistants_to_compact = len(assistant_indices) - self.config.min_preserved_pairs
        assistants_to_compact = (assistants_to_compact // self.config.batch_size) * self.config.batch_size
        
        if assistants_to_compact == 0:
            return [msg.to_full_message() for msg in messages]
            
        # assistant_indices is in reverse order, so:
        # - assistant_indices[0:min_preserved_pairs] = keep FULL (most recent)
        # - assistant_indices[min_preserved_pairs:] = candidates for compaction (older)
        compacted_assistant_indices = set(assistant_indices[self.config.min_preserved_pairs:self.config.min_preserved_pairs + assistants_to_compact])
        
        # Find the earliest compacted assistant message to determine user compaction boundary
        earliest_compacted_assistant = min(compacted_assistant_indices) if compacted_assistant_indices else len(messages)
        
        # Generate result
        result = []
        for i, msg in enumerate(messages):
            if isinstance(msg, AssistantResponseLLMMessage) and i in compacted_assistant_indices:
                # Compact this assistant message
                compacted = msg.to_compact_message()
                if compacted:
                    result.append(compacted)
            elif isinstance(msg, UserInputLLMMessage) and i < earliest_compacted_assistant:
                # Compact all user messages before the earliest compacted assistant
                compacted = msg.to_compact_message()
                if compacted:
                    result.append(compacted)
            else:
                # Keep message as full
                result.append(msg.to_full_message())
                
        return result
```

#### 3. Integration Layer
```python
class InterpreterPrompt:
    def __init__(self, ...):
        # ... existing init code ...
        self.compactor = LLMContextCompactor()
    
    @property  
    def messages(self) -> List[Dict[str, str]]:
        """Get messages with compaction applied."""
        prompt_messages = get_messages_for_prompt(self.prompt)
        messages = []
        messages.append(prompt_messages[0])
        
        # Add other messages...
        # ... existing message setup code ...
        
        # Original call stack messages (as LLMMessage objects)
        call_stack_llm_messages = []
        for frame in self.execution_state.call_stack.frames:
            call_stack_llm_messages.extend(frame.llm_messages)
            
        # Apply compaction - returns Dict[str, str] format ready for LLM API
        compacted_dict_messages = self.compactor.compact_messages(call_stack_llm_messages)
        
        # Log compaction stats
        original_dict_messages = [msg.to_full_message() for msg in call_stack_llm_messages]
        original_size = len(str(original_dict_messages))
        compacted_size = len(str(compacted_dict_messages))
        compression_ratio = compacted_size / original_size if original_size > 0 else 1.0
        
        logger.info(f"LLM Context: {original_size} -> {compacted_size} chars ({compression_ratio:.2%})")
        
        messages.extend(compacted_dict_messages)
        return messages
```

## Configuration Options

### Environment Variables
```bash
# Core compaction settings
LLM_COMPACTION_ENABLED=true
LLM_COMPACTION_MIN_PRESERVED_ASSISTANT_MESSAGES=3
LLM_COMPACTION_BATCH_SIZE=4
```

## Implementation Summary

This simplified design provides:

1. **Polymorphic Compaction**: Each LLMMessage subclass implements its own `to_compact_message()` method
2. **Direct LLM Format**: Returns `Dict[str, str]` format ready for LLM API calls
3. **Flexible Usage**: Uses `to_compact_message()` for compacted pairs, `to_full_message()` for preserved messages
4. **Progressive Batching**: Respects LLM context caching with batch processing
5. **Simple Integration**: Clean integration point in `InterpreterPrompt.messages`
6. **Minimal Configuration**: Only essential parameters
7. **Built-in Monitoring**: Automatic compression ratio logging

The design is clean, maintainable, and follows the existing codebase patterns while providing effective context size management. The `to_compact_message()` method provides a clean abstraction for each message type to define its own compaction behavior while outputting the final LLM API format directly.
