# Playbooks Channel, Stream, and Messaging System Architecture

## Executive Summary

The Playbooks framework implements a sophisticated, event-driven communication architecture built on three foundational abstractions:

1. **Channel** - Unified communication conduit for any number of participants (1:1, multi-party, meetings)
2. **Stream** - Real-time content delivery mechanism for human-facing output
3. **Message** - Immutable data packets flowing through channels between participants

This architecture treats messaging, streaming, and multi-party communication as first-class primitives, enabling seamless agent-to-agent, agent-to-human, and multi-party meeting interactions.

---

## 1. System Architecture Overview

### 1.1 Architectural Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER                           │
│  Playbooks (.pb) → Compilation → PBAsm → Runtime Execution      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      AGENT LAYER                                │
│  AIAgent instances (LocalAIAgent, RemoteAIAgent, HumanAgent)    │
│  • ExecutionState (variables, call stack, session log)          │
│  • MeetingManager (multi-party coordination)                    │
│  • MessagingMixin (message queuing and processing)              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   COMMUNICATION LAYER                           │
│  • Channel (unified communication conduit)                      │
│  • Participant (AgentParticipant, HumanParticipant)             │
│  • Message (immutable message packets)                          │
│  • StreamObserver (streaming event notification)                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    EXECUTION LAYER                              │
│  • Program (orchestrator, channel registry)                     │
│  • AsyncAgentRuntime (asyncio-based concurrency)                │
│  • PythonExecutor (LLM-generated code execution)                │
│  • AsyncMessageQueue (event-driven message delivery)            │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Core Design Principles

1. **Event-Driven Architecture**: Zero polling, pure asyncio.Condition-based message delivery
2. **Unified Communication Model**: Single Channel abstraction handles 1:1, 1:N, and N:N communication
3. **Polymorphic Delivery**: Participant interface enables different delivery mechanisms (agent buffer, human display)
4. **Observable Streaming**: StreamObserver pattern for monitoring real-time content delivery
5. **Immutable Messages**: Messages are read-only data structures with full metadata
6. **Differential Timeouts**: Meeting messages use intelligent timeout logic based on targeting

---

## 2. Data Flow Analysis

### 2.1 Message Creation and Routing

#### Lifecycle: Agent sends message to another agent

```
1. Agent Execution Context
   └─> AIAgent.Say(target, message) or SendMessage(target, message)
       └─> resolve_target(target) → agent_id or meeting_spec
           └─> Program.route_message(sender_id, sender_klass, receiver_spec, message)

2. Channel Resolution
   └─> Program.get_or_create_channel(sender, receiver_spec)
       ├─> Direct: _make_channel_id(sender_id, receiver_id)
       ├─> Meeting: f"meeting_{meeting_id}"
       └─> Create Channel with Participant list if not exists
           └─> Notify all registered channel_creation_callbacks

3. Message Construction
   └─> Message(
           sender_id, sender_klass, content,
           recipient_id, recipient_klass,
           message_type, meeting_id,
           target_agent_ids (for meetings)
       )

4. Channel Delivery
   └─> Channel.send(message, sender_id)
       └─> For each Participant (except sender):
           └─> Participant.deliver(message)
               ├─> AgentParticipant: agent._add_message_to_buffer(message)
               │   └─> AsyncMessageQueue.put(message)
               │       └─> asyncio.Condition.notify_all() [EVENT DRIVEN]
               │
               └─> HumanParticipant: HumanAgent._add_message_to_buffer(message)
                   └─> AsyncMessageQueue.put(message)

5. Message Reception
   └─> AIAgent.WaitForMessage(wait_for_message_from)
       └─> MessagingMixin.WaitForMessage(wait_for_message_from)
           └─> AsyncMessageQueue.get_batch(predicate, timeout, min_messages, max_messages)
               └─> Pure event-driven waiting on asyncio.Condition
               └─> Returns: List[Message]
                   └─> ProcessMessages playbook handles trigger matching, natural language processing
```

### 2.2 Streaming Data Flow (Human-Facing Output)

```
1. Stream Initiation
   └─> AIAgent.Say("human", message) during LLM playbook execution
       └─> start_streaming_say_via_channel(target)
           └─> Program.start_stream(sender_id, sender_klass, receiver_spec, stream_id)
               └─> get_or_create_channel(sender, receiver_spec)
                   └─> Check if any participant is HumanParticipant
                       ├─> Yes: Continue streaming
                       │   └─> Channel.start_stream(stream_id, sender_id, sender_klass, ...)
                       │       └─> Notify all StreamObservers:
                       │           └─> observer.on_stream_start(StreamStartEvent)
                       │
                       └─> No: Return None (skip streaming for agent-to-agent)

2. Stream Chunking
   └─> LLM generates Python code: Say("human", "message")
       └─> Pattern detection in execution/playbook.py
           └─> Extract message content and stream it character-by-character
               └─> Program.stream_chunk(stream_id, sender_id, receiver_spec, chunk)
                   └─> Channel.stream_chunk(stream_id, chunk)
                       └─> Track chunk in _active_streams[stream_id]["chunks"]
                       └─> Notify all StreamObservers:
                           └─> observer.on_stream_chunk(StreamChunkEvent)
                               └─> Terminal/Web UI displays chunk in real-time

3. Stream Completion
   └─> PythonExecutor executes Say("human", message) [Python code execution]
       └─> complete_streaming_say_via_channel(stream_id, target, final_content)
           └─> Program.complete_stream(stream_id, sender_id, receiver_spec, final_content)
               └─> Create final Message object
               └─> Channel.complete_stream(stream_id, final_message)
                   ├─> Pop stream from _active_streams
                   ├─> Notify all StreamObservers:
                   │   └─> observer.on_stream_complete(StreamCompleteEvent)
                   └─> Channel.send(final_message, sender_id)
                       └─> Deliver complete message to all participants
```

### 2.3 Meeting Communication Flow

```
1. Meeting Creation
   └─> AIAgent executes playbook with @meeting: true
       └─> MeetingManager.create_meeting(playbook, kwargs)
           ├─> Generate unique meeting_id
           ├─> Parse required_attendees, optional_attendees from playbook metadata
           ├─> Create Meeting object with owner, participants, invitations
           ├─> Program.create_meeting_channel(meeting_id, participants)
           │   └─> Channel(f"meeting_{meeting_id}", [list of Participants])
           │       └─> Notify all channel_creation_callbacks
           ├─> Send MEETING_INVITATION messages to all attendees
           │   └─> Each invitation routes through respective 1:1 channels
           └─> Wait for required attendees to join (with timeout)
               └─> _wait_for_required_attendees(meeting, timeout_seconds=30)

2. Joining Meeting
   └─> Participant agent receives MEETING_INVITATION message
       └─> ProcessMessages playbook detects invitation
           └─> Execute matching meeting playbook (same name as host's)
               └─> MeetingManager._accept_meeting_invitation(meeting_id, inviter_id, topic, playbook_name)
                   ├─> Update meeting.joined_attendees
                   ├─> Add meeting_id to agent.state.joined_meetings
                   └─> Get/verify meeting channel exists

3. Meeting Broadcast
   └─> Participant calls Say("meeting", message) or Say("meeting", "message")
       └─> Meeting owner: broadcast_to_meeting_as_owner(meeting_id, message)
       └─> Meeting participant: broadcast_to_meeting_as_participant(meeting_id, message)
           └─> Program.route_message(sender_id, sender_klass, f"meeting {meeting_id}", message, MessageType.MEETING_BROADCAST)
               └─> get_or_create_channel(sender, f"meeting {meeting_id}")
                   └─> Channel.send(Message(..., meeting_id=meeting_id, message_type=MEETING_BROADCAST), sender_id)
                       └─> Deliver to all participants except sender
                           └─> Each participant's AsyncMessageQueue.put(message)

4. Meeting Message Reception (Differential Timeouts)
   └─> AIAgent.WaitForMessage(f"meeting {meeting_id}")
       └─> MessagingMixin._get_meeting_timeout(meeting_spec)
           └─> AsyncMessageQueue.peek() to check for targeted messages
               ├─> If targeted (agent mentioned or in target_agent_ids):
               │   └─> timeout = 0.5s (immediate response)
               └─> If not targeted:
                   └─> timeout = 5.0s (passive listening, accumulate chatter)
           └─> AsyncMessageQueue.get_batch(predicate, timeout, ...)
               └─> Returns all messages from meeting within timeout window

5. Meeting Termination
   └─> Meeting owner returns from meeting playbook
       └─> CallStackFrame.pop() removes meeting context
       └─> Meeting remains in registry but is considered "ended"
       └─> Participants can continue until they return from their meeting playbooks
```

---

## 3. Control Flow Analysis

### 3.1 Compilation Pipeline (.pb → .pbasm → Runtime)

```
1. File Loading
   └─> Playbooks.__init__(program_paths, llm_config)
       └─> FileLoader.load_files(program_paths)
           └─> Read .pb and .pbasm files
           └─> Parse frontmatter (YAML metadata)
           └─> Return List[FileCompilationSpec]

2. Compilation Check
   └─> Check if all files are already compiled (.pbasm with valid cache)
       ├─> All compiled: Skip compilation
       │   └─> Use .pbasm content directly
       └─> Some need compilation:
           └─> Compiler.process_files(program_files)
               └─> For each .pb file:
                   └─> Call LLM with preprocess_playbooks.txt prompt
                       ├─> Input: Markdown playbook
                       ├─> Output: PBAsm with line codes (EXE, TNK, QUE, CND, CHK, RET, YLD)
                       └─> Write to .pbasm cache file

3. AST Generation
   └─> markdown_to_ast(pbasm_content, source_file_path)
       └─> Parse H1 (agent definition)
       └─> Parse H2 sections (playbooks):
           ├─> Python playbooks (```python blocks with @playbook decorator)
           │   └─> Extract code, create PythonPlaybook instances
           └─> Markdown playbooks (### Steps sections)
               └─> Parse steps with line codes (01:EXE, 02:QUE, 03:CND, ...)
               └─> Create LLMPlaybook instances with Steps collection

4. Agent Class Generation
   └─> AgentBuilder.create_agent_classes_from_ast(ast)
       └─> For each H1:
           └─> Dynamically create AIAgent subclass
               ├─> klass = agent_name
               ├─> description = agent_description
               ├─> playbooks = Dict[str, Playbook]
               ├─> metadata = { startup_mode, triggers, ... }
               └─> Return Type[AIAgent]

5. Program Initialization
   └─> Program.__init__(event_bus, compiled_program_paths, ...)
       ├─> self.agent_klasses = { "AgentName": AgentClass, ... }
       ├─> self.channels = {}  (Channel registry)
       └─> self.runtime = AsyncAgentRuntime(program=self)

6. Agent Instantiation
   └─> Program.initialize()
       └─> For each agent_klass in agent_klasses.values():
           └─> If should_create_instance_at_start():
               └─> Program.create_agent(agent_klass)
                   ├─> Generate unique agent_id (1000, 1001, 1002, ...)
                   ├─> Instantiate agent with ExecutionState, MeetingManager, MessagingMixin
                   ├─> Register in agents_by_id, agents_by_klass
                   └─> Create Begin__ playbook (auto-generated entry point)
```

### 3.2 Runtime Execution Loop

```
1. Program Start
   └─> Program.run_till_exit()
       └─> Program.begin()
           └─> For each agent in agents:
               └─> AsyncAgentRuntime.start_agent(agent)
                   └─> Create asyncio.Task for _agent_main(agent)
                       └─> Does NOT await - lets tasks run independently

2. Agent Execution Loop
   └─> AsyncAgentRuntime._agent_main(agent)
       └─> agent.initialize()
       └─> agent.begin()
           └─> Execute Begin__ playbook
               ├─> Call all playbooks with @trigger: BGN
               └─> Enter MessageProcessingEventLoop()
                   └─> Infinite loop:
                       ├─> agent.state.variables["$_busy"] = False
                       ├─> messages = await WaitForMessage("*")
                       │   └─> AsyncMessageQueue.get_batch() [BLOCKS UNTIL MESSAGE]
                       ├─> agent.state.variables["$_busy"] = True
                       └─> await execute_playbook("ProcessMessages", [messages])
                           └─> LLM interprets messages and decides action

3. LLM Playbook Execution (Interpreter Pattern)
   └─> AIAgent.execute_playbook("PlaybookName", args, kwargs)
       └─> Pre-execute: Create CallStackFrame, add to call_stack
       └─> LLMPlaybook.execute(*args, **kwargs)
           └─> PlaybookLLMExecution.execute()
               └─> while not done:
                   ├─> Build InterpreterPrompt:
                   │   ├─> Playbook implementation (PBAsm steps)
                   │   ├─> Trigger registry (all available triggers)
                   │   ├─> Session log (execution history)
                   │   ├─> Current state (variables, call stack)
                   │   ├─> Other agents' public playbooks
                   │   └─> Instruction: "Execute PlaybookName from step 01"
                   │
                   ├─> LLM Call (via LLMHelper)
                   │   └─> LLM generates Python code:
                   │       ```python
                   │       # recap: ...
                   │       # plan: ...
                   │       await Step("Playbook:01:QUE")
                   │       $result = await SomePlaybook($arg)
                   │       await Say("user", "Result is $result")
                   │       await Return($result)
                   │       ```
                   │
                   ├─> LLMResponse.create(llm_response, event_bus, agent)
                   │   └─> Parse response, extract Python code
                   │
                   ├─> LLMResponse.execute_generated_code(playbook_args)
                   │   └─> PythonExecutor.execute(code, playbook_args)
                   │       ├─> Build namespace with capture functions:
                   │       │   ├─> Step(), Say(), Var(), Artifact(), Return(), Yld()
                   │       │   ├─> All agent playbooks as callable functions
                   │       │   ├─> Agent proxies (OtherAgent.Playbook syntax)
                   │       │   ├─> Current variables from state
                   │       │   └─> Playbook arguments
                   │       │
                   │       ├─> Preprocess code ($var → var)
                   │       ├─> Inject SetVar() calls for variable assignments
                   │       ├─> Compile to Python bytecode
                   │       ├─> Execute in controlled namespace
                   │       │   └─> Each captured call:
                   │       │       ├─> Step() → Track instruction pointer
                   │       │       ├─> Say() → Route message via Channel
                   │       │       ├─> Var() → Update ExecutionState.variables
                   │       │       ├─> PlaybookCall → execute_playbook() [RECURSIVE]
                   │       │       ├─> Return() → Mark playbook finished
                   │       │       └─> Yld() → Wait for external event
                   │       │
                   │       └─> Return ExecutionResult
                   │           ├─> steps, messages, vars, playbook_calls
                   │           ├─> return_value, playbook_finished
                   │           └─> exit_program, wait_for_user_input
                   │
                   └─> Check ExecutionResult:
                       ├─> If playbook_finished: done = True, break loop
                       ├─> If exit_program: raise ExecutionFinished
                       └─> Otherwise: Continue to next LLM iteration

4. Python Playbook Execution
   └─> AIAgent.execute_playbook("PythonPlaybookName", args, kwargs)
       └─> Pre-execute: Create CallStackFrame
       └─> PythonPlaybook.execute(*args, **kwargs)
           └─> Direct Python function call:
               ├─> If async: await self.func(*args, **kwargs)
               └─> If sync: self.func(*args, **kwargs)
       └─> Post-execute: Pop CallStackFrame, track result

5. Cross-Agent Playbook Calls
   └─> AIAgent1 executes: result = await Agent2.PublicPlaybook($arg)
       └─> Agent proxy intercepts call
           └─> agent1.execute_playbook("Agent2.PublicPlaybook", [arg], {})
               └─> Split "Agent2.PublicPlaybook" → agent_name, playbook_name
               └─> Find agent2 in program.agents
               └─> Check if playbook is public
               └─> agent2.execute_playbook("PublicPlaybook", [arg], {})
                   └─> Execute in agent2's context
                   └─> Return result to agent1
```

### 3.3 Execution Termination

```
1. Normal Termination
   └─> Agent executes: Yld("exit") or Return() from main loop
       └─> raise ExecutionFinished(EXECUTION_FINISHED)
           └─> Caught in AsyncAgentRuntime._agent_main()
               └─> Program.set_execution_finished(reason="normal", exit_code=0)
                   ├─> execution_finished = True
                   ├─> execution_finished_event.set()
                   └─> EventBus.publish(ProgramTerminatedEvent)

2. Cleanup
   └─> Program.run_till_exit() finally block
       └─> Program.shutdown()
           ├─> set_execution_finished()
           ├─> AsyncAgentRuntime.stop_all_agents()
           │   └─> For each agent_id in running_agents:
           │       └─> stop_agent(agent_id)
           │           ├─> Cancel asyncio.Task
           │           ├─> Await task completion
           │           ├─> Notify debug server
           │           └─> Clean up agent resources
           └─> shutdown_debug_server()
```

---

## 4. Dependency Graph

### 4.1 Component Dependencies

```
Program
  ├─> EventBus (event publishing)
  ├─> AsyncAgentRuntime (agent execution)
  │   └─> Dict[agent_id, asyncio.Task]
  ├─> AgentIdRegistry (sequential ID generation)
  ├─> MeetingRegistry (meeting ID generation)
  ├─> Dict[str, Channel] (channel registry)
  │   └─> Channel
  │       ├─> channel_id: str
  │       ├─> participants: List[Participant]
  │       ├─> stream_observers: List[StreamObserver]
  │       └─> _active_streams: Dict[stream_id, stream_info]
  ├─> List[Callable[[Channel], Awaitable[None]]] (channel creation callbacks)
  ├─> Dict[str, Type[AIAgent]] (agent_klasses)
  ├─> Dict[str, List[BaseAgent]] (agents_by_klass)
  ├─> Dict[str, BaseAgent] (agents_by_id)
  └─> DebugServer (optional debugging)

AIAgent (BaseAgent, MessagingMixin)
  ├─> ExecutionState
  │   ├─> CallStack (execution frames)
  │   │   └─> List[CallStackFrame]
  │   │       ├─> InstructionPointer (current step)
  │   │       ├─> LangfuseSpan (tracing)
  │   │       ├─> is_meeting: bool
  │   │       └─> meeting_id: Optional[str]
  │   ├─> Variables (state dictionary with $-prefixed keys)
  │   │   └─> Dict[str, Variable | Artifact]
  │   ├─> SessionLog (execution history)
  │   └─> agents: List[str] (other agent names)
  ├─> MeetingManager
  │   ├─> agent: BaseAgent (reference)
  │   ├─> MeetingMessageHandler
  │   ├─> Dict[str, Meeting] (owned meetings)
  │   └─> Dict[str, JoinedMeeting] (joined meetings)
  ├─> MessagingMixin
  │   ├─> AsyncMessageQueue (_message_queue)
  │   └─> List[Message] (_message_buffer)
  ├─> Dict[str, Playbook] (playbooks)
  │   ├─> LLMPlaybook (markdown-based)
  │   ├─> PythonPlaybook (Python function)
  │   └─> RemotePlaybook (MCP tools)
  ├─> AgentNamespaceManager (isolated execution namespace)
  └─> Program (back-reference for communication routing)

Channel
  ├─> channel_id: str
  ├─> participants: List[Participant]
  │   ├─> AgentParticipant(agent: BaseAgent)
  │   └─> HumanParticipant(agent: HumanAgent | None)
  ├─> stream_observers: List[StreamObserver]
  └─> _active_streams: Dict[stream_id, stream_info]

Message (immutable dataclass)
  ├─> sender_id: str
  ├─> sender_klass: str
  ├─> recipient_id: Optional[str]
  ├─> recipient_klass: Optional[str]
  ├─> content: str
  ├─> message_type: MessageType
  ├─> meeting_id: Optional[str]
  ├─> target_agent_ids: Optional[List[str]]
  ├─> stream_id: Optional[str]
  ├─> id: str (UUID)
  └─> created_at: datetime

AsyncMessageQueue
  ├─> _messages: deque[Message]
  ├─> _condition: asyncio.Condition (event-driven signaling)
  ├─> _closed: bool
  ├─> _waiters: WeakSet[asyncio.Task]
  └─> Statistics (total_messages, total_gets, uptime)

Meeting
  ├─> id: str
  ├─> owner_id: str
  ├─> required_attendees: List[BaseAgent]
  ├─> optional_attendees: List[BaseAgent]
  ├─> joined_attendees: List[BaseAgent]
  ├─> invitations: Dict[agent_id, MeetingInvitation]
  ├─> message_history: List[Message]
  └─> agent_last_message_index: Dict[agent_id, int]
```

### 4.2 Key Interfaces

```python
# Participant Protocol
class Participant(ABC):
    @property
    def id(self) -> str: ...
    @property
    def klass(self) -> str: ...
    async def deliver(self, message: Message) -> None: ...

# StreamObserver Protocol
class StreamObserver(Protocol):
    async def on_stream_start(self, event: StreamStartEvent) -> None: ...
    async def on_stream_chunk(self, event: StreamChunkEvent) -> None: ...
    async def on_stream_complete(self, event: StreamCompleteEvent) -> None: ...
```

---

## 5. Entity Lifecycles

### 5.1 Channel Lifecycle

```
Creation:
  └─> Program.get_or_create_channel(sender, receiver_spec) or create_meeting_channel(meeting_id, participants)
      ├─> Generate channel_id (sorted IDs for consistency)
      ├─> Create Channel(channel_id, [Participant instances])
      ├─> Store in Program.channels[channel_id]
      └─> Notify all channel_creation_callbacks [EVENT-DRIVEN DISCOVERY]

Active State:
  ├─> Channel.send(message, sender_id)
  │   └─> Deliver to all participants except sender
  ├─> Channel.start_stream(stream_id, ...) [HUMAN-ONLY]
  │   └─> Track in _active_streams[stream_id]
  ├─> Channel.stream_chunk(stream_id, chunk)
  │   └─> Append to _active_streams[stream_id]["chunks"]
  └─> Channel.complete_stream(stream_id, final_message)
      ├─> Pop stream from _active_streams
      └─> Send final message to all participants

Termination:
  └─> Channels persist in Program.channels for entire program lifetime
  └─> No explicit cleanup - garbage collected with Program instance
```

### 5.2 Message Lifecycle

```
Creation:
  └─> Message(sender_id, sender_klass, content, recipient_id, recipient_klass, message_type, meeting_id, ...)
      ├─> Immutable dataclass
      ├─> Auto-generated UUID
      └─> Timestamp on creation

Routing:
  └─> Channel.send(message, sender_id)
      └─> For each participant (except sender):
          └─> participant.deliver(message)

Storage:
  ├─> AgentParticipant.deliver(message)
  │   └─> agent._add_message_to_buffer(message)
  │       ├─> AsyncMessageQueue.put(message) [PRIMARY QUEUE]
  │       └─> _message_buffer.append(message) [SYNC BUFFER]
  │
  └─> Meeting.log_message(message) [MEETING HISTORY]
      └─> meeting.message_history.append(message)

Consumption:
  └─> AIAgent.WaitForMessage(wait_for_message_from)
      └─> AsyncMessageQueue.get_batch(predicate, timeout, ...)
          ├─> Event-driven waiting on asyncio.Condition
          ├─> Filter by predicate (sender, meeting, target)
          └─> Remove from queue when matched

Processing:
  └─> ProcessMessages playbook (LLM interpreter)
      ├─> Trigger matching
      ├─> Meeting invitation handling
      └─> Natural language interpretation

Lifecycle End:
  └─> Messages removed from queue after consumption
  └─> Meeting messages remain in meeting.message_history
  └─> No explicit cleanup - garbage collected when references drop
```

### 5.3 Stream Lifecycle (Human-Facing Output Only)

```
Initiation:
  └─> AIAgent.Say("human", message) during LLM playbook execution
      └─> start_streaming_say_via_channel(target)
          └─> Program.start_stream(sender_id, sender_klass, receiver_spec, stream_id)
              └─> Check if HumanParticipant in channel
                  ├─> Yes: Continue
                  │   └─> Channel.start_stream(stream_id, sender_id, ...)
                  │       ├─> _active_streams[stream_id] = { sender_id, chunks: [] }
                  │       └─> StreamObserver.on_stream_start(StreamStartEvent)
                  └─> No: Return None [SKIP STREAMING FOR AGENT-TO-AGENT]

Streaming:
  └─> LLM generates code: Say("human", "message")
      └─> Pattern detection extracts message content
          └─> stream_say_update_via_channel(stream_id, target, chunk)
              └─> Program.stream_chunk(stream_id, sender_id, receiver_spec, chunk)
                  └─> Channel.stream_chunk(stream_id, chunk)
                      ├─> _active_streams[stream_id]["chunks"].append(chunk)
                      └─> StreamObserver.on_stream_chunk(StreamChunkEvent)
                          └─> Terminal/Web UI displays chunk immediately

Completion:
  └─> PythonExecutor executes Say() call [ACTUAL CODE EXECUTION]
      └─> complete_streaming_say_via_channel(stream_id, target, final_content)
          └─> Program.complete_stream(stream_id, sender_id, receiver_spec, final_content)
              └─> Channel.complete_stream(stream_id, final_message)
                  ├─> stream_info = _active_streams.pop(stream_id)
                  ├─> StreamObserver.on_stream_complete(StreamCompleteEvent)
                  └─> Channel.send(final_message, sender_id)
                      └─> Deliver complete message to all participants
```

### 5.4 Agent Lifecycle

```
Definition (Compile-Time):
  └─> .pb file parsed → markdown_to_ast()
      └─> AgentBuilder.create_agent_classes_from_ast(ast)
          └─> Dynamically create Type[AIAgent] subclass
              ├─> klass, description, playbooks, metadata
              └─> Store in Program.agent_klasses

Instantiation (Runtime):
  └─> Program.initialize()
      └─> For each agent_klass with should_create_instance_at_start():
          └─> Program.create_agent(agent_klass)
              ├─> Generate unique agent_id (sequential: 1000, 1001, ...)
              ├─> Instantiate AIAgent subclass
              │   ├─> ExecutionState(event_bus, klass, agent_id)
              │   │   ├─> CallStack()
              │   │   ├─> Variables()
              │   │   └─> SessionLog()
              │   ├─> MeetingManager(agent)
              │   ├─> MessagingMixin.__init__()
              │   │   ├─> AsyncMessageQueue()
              │   │   └─> _message_buffer: List[Message]
              │   ├─> AgentNamespaceManager (isolated execution context)
              │   └─> Deep copy playbooks with instance-specific bindings
              ├─> Register in Program.agents_by_id, agents_by_klass
              └─> Create Begin__ playbook (auto-generated entry point)

Execution:
  └─> AsyncAgentRuntime.start_agent(agent)
      └─> asyncio.create_task(_agent_main(agent))
          └─> agent.initialize()
          └─> agent.begin()
              └─> Execute Begin__ playbook
                  ├─> Call all @trigger: BGN playbooks
                  └─> MessageProcessingEventLoop()
                      └─> Infinite loop until ExecutionFinished

Termination:
  └─> raise ExecutionFinished or Yld("exit")
      └─> Caught in _agent_main(agent)
          └─> AsyncAgentRuntime.stop_agent(agent_id)
              ├─> Cancel asyncio.Task
              ├─> Await task completion
              ├─> Notify debug server (if running)
              ├─> Clean up agent resources
              └─> Remove from running_agents registry
```

### 5.5 Meeting Lifecycle

```
Creation:
  └─> AIAgent executes playbook with @meeting: true
      └─> MeetingManager.create_meeting(playbook, kwargs)
          ├─> Generate unique meeting_id
          ├─> Parse required_attendees, optional_attendees from playbook metadata
          ├─> Create Meeting(id, owner_id, topic, required_attendees, optional_attendees)
          ├─> Store in owner agent's state.owned_meetings
          ├─> Program.create_meeting_channel(meeting_id, participants)
          │   └─> Channel(f"meeting_{meeting_id}", [Participants])
          │       └─> Notify channel_creation_callbacks
          ├─> Send MEETING_INVITATION messages to all attendees
          │   └─> For each attendee:
          │       └─> Program.route_message(..., MessageType.MEETING_INVITATION)
          └─> Wait for required attendees (timeout: 30s)
              └─> Poll meeting.missing_required_attendees() every 0.5s

Active State:
  ├─> Participants join meeting
  │   └─> MeetingManager._accept_meeting_invitation(meeting_id, inviter_id, topic, playbook_name)
  │       ├─> Add to agent.state.joined_meetings
  │       ├─> Update meeting.joined_attendees
  │       └─> Update CallStackFrame.meeting_id
  │
  ├─> Broadcast messages
  │   └─> Program.route_message(..., f"meeting {meeting_id}", ..., MessageType.MEETING_BROADCAST)
  │       └─> Channel.send() delivers to all participants
  │
  ├─> Message reception with differential timeouts
  │   └─> AIAgent.WaitForMessage(f"meeting {meeting_id}")
  │       └─> Check if agent is targeted:
  │           ├─> Targeted: timeout = 0.5s (immediate response)
  │           └─> Not targeted: timeout = 5.0s (passive listening)
  │
  └─> Meeting history tracking
      └─> Meeting.log_message(message)
          └─> message_history.append(message)

Termination:
  └─> Meeting owner returns from meeting playbook
      └─> CallStackFrame.pop() removes meeting context
      └─> Meeting remains in registry (for history)
      └─> Participants can continue until they return from meeting playbooks
      └─> No explicit cleanup - meeting channel persists in Program.channels
```

---

## 6. Key Design Patterns

### 6.1 Unified Communication Model

**Problem**: Need to support 1:1, 1:N, and N:N communication with a consistent interface.

**Solution**: Single Channel abstraction with polymorphic Participant delivery.

```python
# Same interface for all communication types
channel = await program.get_or_create_channel(sender, receiver_spec)
await channel.send(message, sender_id)

# Participant interface handles delivery polymorphism
class AgentParticipant(Participant):
    async def deliver(self, message: Message) -> None:
        await self.agent._add_message_to_buffer(message)

class HumanParticipant(Participant):
    async def deliver(self, message: Message) -> None:
        # Observable pattern - StreamObservers handle display
        if self.agent:
            await self.agent._add_message_to_buffer(message)
```

### 6.2 Event-Driven Message Delivery

**Problem**: Polling-based message checking wastes CPU and increases latency.

**Solution**: Pure asyncio.Condition-based signaling for zero-polling message delivery.

```python
class AsyncMessageQueue:
    async def put(self, message: Message) -> None:
        async with self._condition:
            self._messages.append(message)
            self._condition.notify_all()  # Wake all waiters
    
    async def get_batch(self, predicate, timeout, ...) -> List[Message]:
        async with self._condition:
            while True:
                # Check for matching messages
                if messages_found:
                    return messages
                # No matches - wait for new messages (event-driven)
                await asyncio.wait_for(self._condition.wait(), timeout=timeout)
```

### 6.3 Observable Streaming

**Problem**: Need to display LLM-generated content in real-time across different frontends (terminal, web).

**Solution**: StreamObserver pattern with three lifecycle events.

```python
class StreamObserver(Protocol):
    async def on_stream_start(self, event: StreamStartEvent) -> None: ...
    async def on_stream_chunk(self, event: StreamChunkEvent) -> None: ...
    async def on_stream_complete(self, event: StreamCompleteEvent) -> None: ...

# Terminal display implementation
class TerminalStreamObserver:
    async def on_stream_chunk(self, event: StreamChunkEvent) -> None:
        print(event.chunk, end='', flush=True)
```

### 6.4 Differential Timeouts

**Problem**: In meetings, targeted agents need immediate response, non-targeted agents should accumulate chatter.

**Solution**: Dynamic timeout based on message targeting.

```python
async def _get_meeting_timeout(self, meeting_spec: str) -> float:
    # Check if agent is targeted in pending messages
    targeted_message = await self._message_queue.peek(
        lambda m: (
            m.meeting_id == meeting_id and
            (m.target_agent_ids and self.id in m.target_agent_ids)
        )
    )
    if targeted_message:
        return 0.5  # Immediate response
    else:
        return 5.0  # Accumulate chatter
```

### 6.5 LLM-as-CPU Execution

**Problem**: Need to execute natural language instructions reliably on LLMs.

**Solution**: Compilation to PBAsm (assembly language for LLMs) with interpreter pattern.

```
1. Compilation: .pb (high-level) → .pbasm (assembly)
   - Each step annotated with opcode (EXE, TNK, QUE, CND, CHK, RET, YLD)
   - Line numbering for step addressing (01, 01.01, 01.01.01)
   
2. Interpretation: LLM repeatedly called with:
   - Playbook implementation (PBAsm)
   - Current state (variables, call stack, session log)
   - Instruction: "Execute next steps from line N"
   
3. Code Generation: LLM outputs Python code:
   await Step("Playbook:01:QUE")
   $result = await SomePlaybook($arg)
   await Say("user", f"Result: {$result}")
   
4. Execution: PythonExecutor runs generated code
   - Captures Step(), Say(), Var(), etc.
   - Routes messages through channels
   - Updates execution state
   
5. Loop: Repeat until playbook completes
```

---

## 7. Critical Implementation Details

### 7.1 Channel ID Generation

```python
def _make_channel_id(self, sender_id: str, receiver_id: str) -> str:
    """Create deterministic channel ID using sorted IDs."""
    ids = sorted([sender_id, receiver_id])
    return f"channel_{ids[0]}_{ids[1]}"
```

**Why sorted?** Ensures same channel is used regardless of who sends first.

### 7.2 Agent-to-Agent Streaming Optimization

```python
async def start_stream(self, sender_id, sender_klass, receiver_spec, stream_id):
    channel = await self.get_or_create_channel(sender_agent, receiver_spec)
    
    # Check if any participant is human
    has_human = any(isinstance(p, HumanParticipant) for p in channel.participants)
    
    if not has_human:
        return None  # SKIP STREAMING for agent-to-agent
    
    # Human recipient - start streaming
    await channel.start_stream(stream_id, sender_id, ...)
    return stream_id
```

**Why skip streaming?** Agent-to-agent messages don't need real-time display. Direct delivery is faster.

### 7.3 Message Buffer Synchronization

```python
class MessagingMixin:
    async def _add_message_to_buffer(self, message: Message) -> None:
        await self._message_queue.put(message)  # Primary queue
        self._message_buffer.append(message)    # Sync buffer for compatibility
```

**Why two buffers?** `_message_queue` is event-driven primary storage. `_message_buffer` maintains backwards compatibility with agent_chat.py and other legacy code.

### 7.4 Meeting Invitation Flow

```python
# 1. Owner creates meeting
await MeetingManager.create_meeting(playbook, kwargs)
    # Sends MEETING_INVITATION to each attendee via 1:1 channels
    for attendee in all_attendees:
        await program.route_message(
            sender_id=owner_id,
            receiver_spec=SpecUtils.to_agent_spec(attendee.id),
            message=invitation_text,
            message_type=MessageType.MEETING_INVITATION,
            meeting_id=meeting.id
        )

# 2. Attendee receives invitation in their message queue
messages = await agent.WaitForMessage("*")
# ProcessMessages playbook detects MessageType.MEETING_INVITATION

# 3. Attendee auto-joins by executing matching meeting playbook
await agent.execute_playbook("SameMeetingPlaybookName", kwargs={
    "meeting_id": meeting.id,
    "inviter_id": owner_id,
    "topic": topic
})

# 4. Meeting playbook execution triggers auto-acceptance
if meeting_id and meeting_id not in self.state.joined_meetings:
    await self.meeting_manager._accept_meeting_invitation(
        meeting_id, inviter_id, topic, playbook_name
    )
```

**Key insight**: Meetings use natural playbook execution for joining, not special API calls.

### 7.5 Call Stack and Meeting Context

```python
class CallStackFrame:
    instruction_pointer: InstructionPointer
    langfuse_span: Any  # Tracing
    is_meeting: bool
    meeting_id: Optional[str]

def get_current_meeting_from_call_stack(self) -> Optional[str]:
    """Walk call stack from top to find meeting context."""
    for frame in reversed(self.call_stack.frames):
        if frame.is_meeting and frame.meeting_id:
            return frame.meeting_id
    return None
```

**Why call stack?** Meeting context is implicitly inherited by nested playbook calls.

---

## 8. Performance Characteristics

### 8.1 Message Delivery Latency

- **Event-driven**: O(1) notification via asyncio.Condition.notify_all()
- **Predicate matching**: O(n) where n = queue size
- **Channel routing**: O(1) dictionary lookup
- **Participant delivery**: O(p) where p = number of participants

### 8.2 Memory Usage

- **Messages**: Immutable, small footprint (~500 bytes each)
- **Channels**: Lazy creation, persisted for program lifetime
- **Streams**: Ephemeral, only during active streaming
- **Message queue**: Bounded by program lifetime, typically < 1000 messages

### 8.3 Concurrency Model

- **Pure asyncio**: No threads, no locks, no race conditions
- **Independent agent execution**: Each agent runs as separate asyncio.Task
- **Shared state**: Program.channels, agents_by_id (single-threaded access pattern)
- **Synchronization**: asyncio.Condition for message queues, asyncio.Event for program termination

---

## 9. Extension Points

### 9.1 Custom Stream Observers

```python
class CustomStreamObserver:
    async def on_stream_start(self, event: StreamStartEvent) -> None:
        # Custom logic: logging, metrics, external API calls
        pass
    
    async def on_stream_chunk(self, event: StreamChunkEvent) -> None:
        # Custom logic: WebSocket push, database logging
        pass
    
    async def on_stream_complete(self, event: StreamCompleteEvent) -> None:
        # Custom logic: analytics, archiving
        pass

# Register observer
channel.add_stream_observer(CustomStreamObserver())
```

### 9.2 Channel Creation Callbacks

```python
async def on_new_channel_created(channel: Channel) -> None:
    """Called immediately when new channel is created."""
    # Custom logic: monitoring, logging, UI updates
    if channel.is_meeting:
        print(f"New meeting channel: {channel.channel_id}")
    else:
        print(f"New 1:1 channel: {channel.channel_id}")

# Register callback
program.register_channel_creation_callback(on_new_channel_created)
```

### 9.3 Custom Participant Types

```python
class RemoteParticipant(Participant):
    """Participant connected via network."""
    
    @property
    def id(self) -> str:
        return self.remote_id
    
    @property
    def klass(self) -> str:
        return "RemoteAgent"
    
    async def deliver(self, message: Message) -> None:
        # Send message over network
        await self.websocket.send_json(message.to_dict())
```

### 9.4 Message Type Extensions

```python
class MessageType(enum.Enum):
    DIRECT = "direct"
    MEETING_BROADCAST = "meeting_broadcast"
    # Custom types:
    SYSTEM_NOTIFICATION = "system_notification"
    AGENT_STATUS_UPDATE = "agent_status_update"
    DEBUG_TRACE = "debug_trace"
```

---

## 10. Testing Strategies

### 10.1 Unit Testing

```python
# Test message routing
async def test_message_routing():
    program = create_test_program()
    sender = program.agents_by_id["1000"]
    receiver = program.agents_by_id["1001"]
    
    await program.route_message(
        sender_id=sender.id,
        sender_klass=sender.klass,
        receiver_spec=SpecUtils.to_agent_spec(receiver.id),
        message="Test message"
    )
    
    messages = await receiver.WaitForMessage(sender.id)
    assert len(messages) == 1
    assert messages[0].content == "Test message"
```

### 10.2 Integration Testing

```python
# Test meeting flow
async def test_meeting_creation_and_join():
    program = create_test_program()
    owner = program.agents_by_id["1000"]
    attendee = program.agents_by_id["1001"]
    
    # Create meeting
    meeting = await owner.meeting_manager.create_meeting(playbook, kwargs)
    
    # Attendee receives invitation
    messages = await attendee.WaitForMessage("*")
    assert messages[0].message_type == MessageType.MEETING_INVITATION
    
    # Attendee joins
    await attendee.meeting_manager._accept_meeting_invitation(meeting.id, owner.id, "Test Meeting", "TestPlaybook")
    
    # Broadcast message
    await owner.meeting_manager.broadcast_to_meeting_as_owner(meeting.id, "Hello meeting")
    
    # Attendee receives broadcast
    messages = await attendee.WaitForMessage(f"meeting {meeting.id}")
    assert messages[0].content == "Hello meeting"
```

### 10.3 Performance Testing

```python
# Test message throughput
async def test_message_throughput():
    program = create_test_program()
    sender = program.agents_by_id["1000"]
    receiver = program.agents_by_id["1001"]
    
    num_messages = 10000
    start_time = time.time()
    
    for i in range(num_messages):
        await program.route_message(
            sender_id=sender.id,
            sender_klass=sender.klass,
            receiver_spec=SpecUtils.to_agent_spec(receiver.id),
            message=f"Message {i}"
        )
    
    elapsed = time.time() - start_time
    throughput = num_messages / elapsed
    print(f"Throughput: {throughput:.0f} messages/second")
    assert throughput > 1000  # Expect > 1000 msg/sec
```

---

## 11. Debugging and Observability

### 11.1 Debug Server Integration

The framework includes a debug server (DAP protocol) for IDE integration:

```python
# Start debug server
await program.start_debug_server(host="127.0.0.1", port=7529, stop_on_entry=False)

# Debug features:
- Step-by-step playbook execution
- Breakpoints on PBAsm lines
- Variable inspection
- Call stack visualization
- Agent thread tracking
```

### 11.2 Tracing with Langfuse

Every playbook call is traced:

```python
# Trace hierarchy
Program
  └─> Agent.Begin__()
      └─> Agent.ProcessMessages([messages])
          └─> Agent.HandleQuery($query)
              └─> Agent.FetchData($url)
                  └─> RemotePlaybook.HttpGet($url)
```

### 11.3 Logging

```python
from playbooks.debug_logger import debug

# Structured logging
debug("Routing message",
      sender_id=sender_id,
      receiver_spec=receiver_spec,
      message_length=len(message))

# Output:
# [2024-01-01 12:00:00] Routing message | sender_id=1000 | receiver_spec=agent 1001 | message_length=42
```

---

## 12. Comparison with Traditional Systems

| Aspect | Traditional RPC/Message Queue | Playbooks Framework |
|--------|------------------------------|---------------------|
| **Communication Model** | Explicit send/receive, queues | Unified Channel abstraction |
| **Concurrency** | Threads, locks, race conditions | Pure asyncio, no locks |
| **Message Delivery** | Polling or callback registration | Event-driven (asyncio.Condition) |
| **Streaming** | WebSocket/Server-Sent Events | StreamObserver pattern |
| **Multi-Party** | Pub/Sub topics | Meeting channels with differential timeouts |
| **Type Safety** | Protobuf/JSON schemas | Message dataclass, type hints |
| **Observability** | External APM tools | Built-in Langfuse tracing, debug server |
| **Execution Model** | Compiled binary or interpreted | LLM-as-CPU with PBAsm |

---

## 13. Future Enhancements

### 13.1 Persistent Message Storage

Currently messages are in-memory only. Future: database-backed message history.

```python
class PersistentChannel(Channel):
    async def send(self, message: Message, sender_id: str) -> None:
        await super().send(message, sender_id)
        await self.message_store.save(message)
```

### 13.2 Message Acknowledgment

Add explicit acknowledgment for reliable delivery:

```python
class Message:
    ack_required: bool = False
    ack_timeout: float = 30.0

await channel.send(message, sender_id)
ack = await channel.wait_for_ack(message.id, timeout=message.ack_timeout)
```

### 13.3 Channel Encryption

End-to-end encryption for sensitive communications:

```python
class EncryptedChannel(Channel):
    def __init__(self, channel_id, participants, encryption_key):
        super().__init__(channel_id, participants)
        self.encryption_key = encryption_key
    
    async def send(self, message: Message, sender_id: str) -> None:
        encrypted_content = encrypt(message.content, self.encryption_key)
        encrypted_message = message.copy(content=encrypted_content)
        await super().send(encrypted_message, sender_id)
```

### 13.4 Cross-Process Agent Communication

Support agents running in different processes:

```python
class RemoteAgentParticipant(Participant):
    async def deliver(self, message: Message) -> None:
        # Serialize and send over IPC/network
        await self.transport.send(message.to_dict())
```

---

## Conclusion

The Playbooks framework implements a sophisticated, event-driven communication architecture that treats messaging, streaming, and multi-party coordination as unified, first-class primitives. Key innovations include:

1. **Unified Channel Model**: Single abstraction handles all communication patterns
2. **Event-Driven Delivery**: Zero-polling, asyncio.Condition-based signaling
3. **Observable Streaming**: Real-time content delivery with observer pattern
4. **Differential Timeouts**: Intelligent meeting message handling
5. **LLM-as-CPU**: Natural language execution on PBAsm assembly language

This architecture enables seamless agent-to-agent, agent-to-human, and multi-party interactions while maintaining performance, observability, and extensibility.

