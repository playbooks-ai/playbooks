# Agent Threading Architecture - PRD

## Current Architecture

**Hybrid Threading Model**: Human agents threaded, AI agents synchronous.

### Core Components

**BaseAgent**: Behavior-focused, no threading concerns
```python
class BaseAgent:
    def __init__(self, klass: str, agent_id: str = None):
        self._message_buffer = []  # Simple message buffer
    
    async def WaitForMessage(self, source_agent_id: str):
        # Polls _message_buffer directly
```

**AgentRuntime**: Execution management  
```python
class AgentRuntime:
    def start_agent(self, agent):
        # Creates thread only for human agent
    
    def send_message_to_agent(self, agent_id: str, message):
        # Routes to threaded agent queues
```

**Program**: Hybrid execution
```python
async def begin(self):
    for agent in self.agents:
        if agent.id == "human":
            self.runtime.start_agent(agent)  # Thread
        else:
            await agent.initialize()  # Sync
    
    ai_agents = [a for a in self.agents if a.id != "human"]
    await asyncio.gather(*[a.begin() for a in ai_agents])

def route_message(self, sender_id, target_id, message):
    if target_agent.id == "human":
        self.runtime.send_message_to_agent(target_id, message)  # Queue
    else:
        target_agent._message_buffer.append(message)  # Direct
```

## Design Decisions

1. **Separation of Concerns**: Runtime manages execution, Agents define behavior
2. **Minimal Threading**: Only thread what benefits (human agent responsiveness)
3. **Preserve AI Patterns**: AI agents run synchronously as designed
4. **Smart Routing**: Direct buffer for AI, queue for human

## Validation

- ✅ All 11 meeting tests pass
- ✅ test_example_02 works (AI receives user input)
- ✅ No performance degradation
- ✅ Backward compatibility maintained

## Next Phases

### Phase 1: Network Distribution
- Abstract message transport in AgentRuntime
- Add remote agent discovery
- Implement network-based message routing

### Phase 2: Enhanced Monitoring  
- Per-agent metrics collection
- Runtime health monitoring
- Debug utilities for distributed agents

### Phase 3: Advanced Threading
- Event-driven AI agent execution (if needed)
- Multi-human agent support
- Load balancing across agent instances

## Files Modified
- `src/playbooks/agents/base_agent.py` - Clean agent behavior
- `src/playbooks/program.py` - AgentRuntime + hybrid execution  
- `src/playbooks/simple_message.py` - Message structure