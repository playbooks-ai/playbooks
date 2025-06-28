# Agent Threading Architecture - Product Requirements Document

## Executive Summary

This document outlines the transition from the current async-based agent architecture to a **thread-per-agent model with async I/O within each agent**. This change will enable distributed agent deployment, simplify the mental model, and improve fault isolation while maintaining performance for I/O-bound operations.

## Current State Analysis

### Existing Architecture (Async-Based)
- **Centralized event loop** coordinating all agents
- **Complex async inbox management** with waiting modes and timeouts
- **Shared meeting state** managed at program level
- **Tightly coupled agent coordination** through async/await patterns

### Recent Achievements
- ✅ **Reorganized meeting system** into clean modular classes in `src/playbooks/meetings/`
- ✅ **All 11 meeting tests passing** with progressive complexity
- ✅ **Working tic-tac-toe game** demonstrating full meeting functionality
- ✅ **Eliminated new/old system terminology** for cleaner codebase

## Target Architecture (Thread-Per-Agent)

### Core Principles
1. **One thread per agent** with independent execution
2. **Async I/O within each agent** for LLM calls, APIs, etc.
3. **Decentralized state management** - each agent maintains its own view
4. **Message-based communication** via thread-safe queues
5. **Distributed-ready design** for multi-machine deployment

### Key Architectural Changes

#### Agent Structure
```python
class Agent:
    def __init__(self, agent_id: str):
        self.message_queue = queue.Queue()  # Thread-safe
        self.thread = None
        self.running = False
        self.meeting_views = {}  # Own meeting state
        
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.main_loop)
        self.thread.start()
    
    def main_loop(self):
        # Create async loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self.running:
            try:
                message = self.message_queue.get(timeout=0.1)
                if message:
                    loop.run_until_complete(self.process_message(message))
            except queue.Empty:
                continue  # Keep polling
    
    async def process_message(self, message):
        # Can still await LLM calls, API calls, etc.
        response = await self.llm_call(...)
```

#### Simplified Program State
```python
class Program:
    def __init__(self):
        self.agents_lock = threading.RLock()
        self.agents_by_id = {}  # Only shared state needed
        # No shared meeting state - each agent manages its own!
```

## Benefits Analysis

### ✅ Advantages

**🔹 Simplified Concurrency Model**
- Each agent is truly independent with its own execution context
- No complex async coordination between agents required
- Natural isolation prevents agents from interfering with each other
- Easier mental model: "each agent is a simple loop processing messages"

**🔹 Distributed System Readiness**
- Each agent can run on a different machine
- Message-based communication works across network boundaries
- Natural fit for microservice deployment patterns
- Easier to implement agent discovery and routing

**🔹 Better Fault Isolation**
- Agent crashes don't affect other agents
- Thread-local error handling and recovery
- Each agent can have independent monitoring and health checks
- Graceful degradation when agents fail

**🔹 Simplified Message Processing**
- No complex inbox management with async waiting
- Simple blocking queue operations with timeouts
- Cleaner separation between waiting and processing
- Each agent processes at its own pace

**🔹 Enhanced Debugging & Monitoring**
- Each agent thread can be monitored independently
- Thread-local logging and debugging capabilities
- Easier to pause/inspect individual agents
- Natural boundaries for per-agent metrics

### ⚠️ Challenges & Mitigations

**🔹 Threading Complexity**
- **Challenge**: Thread-safe data structures needed for shared state
- **Mitigation**: Minimize shared state to just agent registry
- **Challenge**: Potential deadlocks in synchronous communication
- **Mitigation**: Use timeout-based communication, avoid hard waits

**🔹 Resource Overhead**
- **Challenge**: Memory overhead (~8MB per thread)
- **Mitigation**: Acceptable for realistic agent counts (<100)
- **Challenge**: Context switching costs
- **Mitigation**: Agents spend most time waiting for I/O anyway

**🔹 Testing Complexity**
- **Challenge**: Non-deterministic execution order
- **Mitigation**: Use thread coordination primitives in tests
- **Challenge**: Race conditions in tests
- **Mitigation**: Implement deterministic test patterns

## Implementation Plan

### Phase 1: Thread-Safe Infrastructure

**🎯 Goal**: Basic agent threading with message queues

**Tasks**:
1. **Agent Thread Management**
   - Convert `BaseAgent` to run in its own thread
   - Implement `start()`, `stop()`, and `main_loop()` methods
   - Add graceful shutdown handling

2. **Thread-Safe Message Queues**
   - Replace async inboxes with `queue.Queue`
   - Implement timeout-based message polling
   - Add message routing through program

3. **Minimal Shared State**
   - Thread-safe agent registry for discovery
   - Remove shared meeting state from program
   - Each agent maintains independent state

**Validation Criteria**:
- Agents start and stop cleanly
- Basic message passing between agents works
- No shared state corruption

### Phase 2: Message Processing Redesign

**🎯 Goal**: Robust inter-agent communication

**Tasks**:
1. **Agent Main Loop**
   - Implement synchronous message queue polling with timeouts
   - Maintain async event loop within each agent thread
   - Handle message processing errors gracefully

2. **Inter-Agent Communication**
   - Thread-safe message routing through program
   - Remove complex async coordination patterns
   - Add message correlation IDs for request/response

3. **Communication Patterns**
   - Implement broadcast messaging
   - Add point-to-point messaging
   - Handle message ordering and delivery guarantees

**Validation Criteria**:
- Agents can send/receive messages reliably
- Request/response patterns work
- Broadcast messages reach all agents

### Phase 3: Meeting System Adaptation

**🎯 Goal**: Port meeting system to threaded architecture

**Tasks**:
1. **Decentralized Meeting State**
   - Move meeting state from program to individual agents
   - Each agent maintains its own "view" of meetings
   - Implement eventual consistency through message passing

2. **Meeting Message Handling**
   - Adapt `MeetingMessageHandler` for threaded model
   - Update meeting invitation and response flows
   - Handle participant list divergence gracefully

3. **Meeting Lifecycle Management**
   - Port meeting creation, invitation, and cleanup
   - Update `MeetingManager` for thread-safe operations
   - Ensure meeting messages work across agent threads

**Validation Criteria**:
- All 11 existing meeting tests pass
- Tic-tac-toe game works with threaded agents
- Meeting state consistency maintained

### Phase 4: Error Handling & Monitoring

**🎯 Goal**: Robust error management and observability

**Tasks**:
1. **Agent Error Management**
   - Implement error broadcasting to all agents
   - Add agent health monitoring and heartbeats
   - Graceful handling of agent failures and recovery

2. **System Monitoring**
   - Add per-agent metrics collection
   - Implement centralized logging coordination
   - Create debugging utilities for threaded execution

3. **Testing Framework Updates**
   - Add thread coordination utilities for tests
   - Implement deterministic test execution patterns
   - Update all meeting tests for threaded model

**Validation Criteria**:
- Agent failures are detected and reported
- System remains stable when agents crash
- Tests run reliably with threading

### Phase 5: Distributed Preparation

**🎯 Goal**: Network-ready architecture

**Tasks**:
1. **Network-Ready Architecture**
   - Abstract message transport layer
   - Implement serializable message formats
   - Add agent discovery mechanisms

2. **Configuration Management**
   - Support for remote agent addresses
   - Network topology configuration  
   - Connection management and retries

3. **Deployment Tooling**
   - Container-ready agent packaging
   - Multi-machine deployment scripts
   - Service discovery integration

**Validation Criteria**:
- Agents can run on separate machines
- Network failures are handled gracefully
- System scales across multiple nodes

## Change Management Strategy

### Git Branching Approach
```bash
# 1. Commit current meeting work
git add .
git commit -m "Complete meetings system reorganization with working tests

- Consolidated meeting functionality into src/playbooks/meetings/
- 11/11 meeting tests passing including tic-tac-toe game
- Clean separation: Meeting, MeetingManager, MeetingMessageHandler, MeetingRegistry
- Removed new/old system terminology
- Ready for threading architecture transition"

# 2. Create threading branch
git checkout -b feature/agent-threading

# 3. Implement Phases 1-5 with incremental commits

# 4. Merge back when complete
git checkout meetings  # or master
git merge feature/agent-threading
```

### Risk Mitigation
- **Preserve Meeting Investment**: All meeting test logic remains valid
- **Incremental Validation**: Each phase has clear success criteria
- **Fallback Strategy**: Can return to async branch if needed
- **Integration Testing**: Meeting functionality serves as threading validation

### Success Criteria for Merge
1. **All 11 meeting tests pass** in threaded model
2. **Tic-tac-toe game works** with threaded agents
3. **Performance is acceptable** (no significant degradation)
4. **Architecture is distributed-ready** (network abstraction in place)
5. **Error handling is robust** (agent failures handled gracefully)

## Technical Architecture Details

### Thread Lifecycle Management
```python
class AgentThreadManager:
    def __init__(self):
        self.agents = {}
        self.shutdown_event = threading.Event()
    
    def start_agent(self, agent):
        agent.start()
        self.agents[agent.id] = agent
    
    def shutdown_all(self):
        self.shutdown_event.set()
        for agent in self.agents.values():
            agent.stop()
            agent.thread.join(timeout=5.0)
```

### Message Transport Abstraction
```python
class MessageTransport:
    def send_message(self, sender_id: str, target_id: str, message: dict):
        """Abstract interface for message delivery"""
        pass

class LocalQueueTransport(MessageTransport):
    """Local thread-safe queue implementation"""
    pass

class NetworkTransport(MessageTransport):
    """Network-based message delivery for distributed agents"""
    pass
```

### Decentralized Meeting State
```python
class AgentMeetingView:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.meetings = {}  # meeting_id -> MeetingView
    
    def update_meeting_participants(self, meeting_id: str, participants: List[str]):
        """Update local view of meeting participants"""
        # Eventually consistent - may differ between agents temporarily
        pass
```

## Performance Considerations

### Memory Usage
- **Thread overhead**: ~8MB per agent thread
- **Queue memory**: Bounded message queues to prevent memory leaks
- **Realistic scale**: 10-100 agents per machine

### CPU Usage
- **Context switching**: Minimal impact due to I/O-bound workloads
- **Async within thread**: Maintains efficiency for LLM calls
- **Message processing**: Simple queue operations are very fast

### Network Bandwidth (Future)
- **Message serialization**: JSON or Protocol Buffers
- **Compression**: For large messages between distributed agents
- **Batching**: Group small messages for efficiency

## Migration Timeline

### Week 1: Infrastructure (Phases 1-2)
- Convert agents to threaded model
- Implement message queue system
- Basic inter-agent communication

### Week 2: Meeting System (Phase 3)
- Port meeting classes to threaded model
- Update all meeting tests
- Validate tic-tac-toe game

### Week 3: Polish (Phase 4)
- Error handling and monitoring
- Testing framework updates
- Performance optimization

### Week 4: Distribution Prep (Phase 5)
- Network abstraction layer
- Configuration management
- Documentation and deployment guides

## Conclusion

The transition to a thread-per-agent architecture will significantly simplify the system's mental model while preparing it for distributed deployment. By maintaining async I/O within each agent thread, we preserve performance benefits while gaining the isolation and scalability advantages of threading.

The existing meeting system serves as an excellent integration test for this architecture change, ensuring that our threading implementation maintains all current functionality while opening the door to distributed multi-agent systems.

**Next Steps**: Implement this plan incrementally, using the meeting test suite as validation criteria for each phase of the threading transition.