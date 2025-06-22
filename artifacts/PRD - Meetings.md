# AI Agent to AI Agent 2-Way Communication: Product Requirements & Technical Design

## Executive Summary

This document specifies the design and implementation of N-way multi-agent communication for the Playbooks framework. The design enables sophisticated multi-agent coordination through a "meeting" metaphor while maintaining the natural language programming model that makes Playbooks intuitive.

## Table of Contents
1. [Product Requirements](#product-requirements)
2. [Technical Design](#technical-design)
3. [Implementation Details](#implementation-details)
4. [API Reference](#api-reference)
5. [Examples](#examples)
6. [Implementation Phases](#implementation-phases)

---

## Product Requirements

### Goals
1. Enable AI agents to communicate and collaborate with each other
2. Support both simple message exchanges and complex multi-agent coordination
3. Maintain natural language authoring of playbooks
4. Preserve backward compatibility where reasonable

### Core Concepts

#### Communication Types
1. **Ad-hoc Messages**: Direct agent-to-agent messages (current implementation)
2. **Meetings**: Multi-agent coordinated interactions via meeting playbooks (new feature described in this document)

#### Key Principles
- Every agent (including Human) is treated uniformly in the communication model
- Meetings are tied to playbook execution, not separate objects
- Single-threaded agents can only participate in one context at a time
- Natural language instructions map directly to system operations via playbooks assembly language compiler, the Playbooks runtime and the interpreter

### User Experience

#### Natural Language Patterns
```markdown
# Simple messaging -- Say() must have two arguments: target and message
## To human by default
- Say("Hello") -- NOT SUPPORTED any more
- Say hello to user
- Say("user", "Hello")
- Say("Human", "Hello")
- Explain the report to the user

## To specific agent
- Say("FlightAgent", "Find flights to Paris")
- Ask FlightAgent to find flights to Paris
- Find flights to Paris # this relies on interpreter to map to appropriate agent

# Meeting coordination

## Start a meeting
- Have a travel planning meeting with FlightAgent and HotelAgent
- Have a travel planning meeting with FlightAgent, HotelAgent and AccountantAgent

## Add an agent to a meeting
From inside the TravelPlanning playbook
- Add AccountantAgent to this meeting

## Leave a meeting
From inside the TravelPlanning playbook, use any of the following:
- Leave meeting
- return
- Leave meeting 123456

## End a meeting
From inside the TravelPlanning playbook, use any of the following:
- End meeting
- End meeting 123456
- return # when last participant leaves the meeting

# Waiting for responses
- YLD for user  # Wait for human input
- YLD for meeting  # Wait for meeting messages
- YLD for agent TaxAgent  # Wait for specific agent
```

---

## Technical Design

### Identity Management

#### Agent IDs
- **Format**: Numeric (e.g., 12345678)
- **Scope**: Unique within program execution session
- **Generation**: Framework-generated on agent instantiation, sequential, starting at 1000

#### Meeting IDs
- **Format**: Numeric (e.g., 123456)
- **Scope**: Unique within program execution session
- **Generation**: Framework-generated when meeting playbook starts, sequential, starting at 100

### State Representation

The execution state visible to LLMs includes:

```json
{
  "variables": {...},
  "artifacts": {...},
  "call_stack": [
    "GetTaxCodes:02:YLD",
    "ResolveTaxCodeMeeting:03:EXE[meeting 123456]",
    "AccountManagement:05:QUE",
    "Main:03:QUE"
  ],
  "agents": [
    {"type": "TaxAgent", "agent_id": "12345678"},
    {"type": "Accountant", "agent_id": "45671234"},
    {"type": "Supervisor", "agent_id": "45671111"},
    {"type": "Human", "agent_id": "human"}
  ],
  "meetings": [
    {
      "meeting_id": "123456",
      "participants": [
        {"type": "Supervisor", "agent_id": "45671111"},
        {"type": "Accountant", "agent_id": "45671234"}, 
        {"type": "Human", "agent_id": "human"}
      ]
    }
  ]
}
```

### Communication Model

#### Say() Function
```python
Say(target: str, message: str)
```

**Routing Rules**:
1. **No target specified**: e.g. `Say("Hello")` -- NOT SUPPORTED any more
2. **Target specified**:
   - Numeric → meeting ID, e.g. `Say("meeting 123456", "Hello")`
   - Numeric → agent ID, e.g. `Say("agent 12345678", "Hello")`
   - String → agent type, e.g. `Say("TaxAgent", "Hello")`
   - "Human" or "user" → human agent, e.g. `Say("Human", "Hello")` or `Say("user", "Hello")`

Note that the interpreter LLM will have to decide how to generate the Say() call intelligently. For example, 
- when not in a meeting, instruction "Ask TaxAgent for standarized deduction amount" should be translated to `Say("TaxAgent", "What is the standarized deduction amount?"); YLD for TaxAgent`, but
- when in a meeting, the same instruction should be translated to `Say("meeting", "Tax agent, what is the standarized deduction amount?"); YLD for meeting`. This is to simulate talking with TaxAgent in the presence of other participants.

What about private messages while in a meeting? The instruction should make that explicit. For example, "Privately ask TaxAgent for standarized deduction amount" should be translated to `Say("TaxAgent", "What is the standarized deduction amount?"); YLD for TaxAgent`

#### YLD Function
```markdown
YLD for <source>
```

**Source Options**:
- `YLD for meeting` → current meeting (top of stack)
- `YLD for meeting 123456` → specific meeting
- `YLD for agent` → agent that you sent 1:1 message to last, don't fallback to Human
- `YLD for agent 12345678` → specific agent instance
- `YLD for agent TaxAgent` → any agent of type TaxAgent
- `YLD for user` (current implementation) or `YLD for Human` → human agent

### Meeting Architecture

#### Meeting Definition
- Meetings are playbook executions with `meeting: true` metadata
- No separate meeting objects - meetings exist through playbook execution
- Meeting lifecycle tied to playbook execution lifecycle

#### Meeting Playbook Structure
```markdown
## Travel Planning
meeting: true
required_attendees: [TaxAgent, Accountant]
optional_attendees: [Supervisor]

[Instructions how to process messages and respond appropriately in the meeting]
### Triggers
- When invited to travel planning meeting

### Steps
- Introduce yourself
- If you initiated the meeting, explain the meeting purpose and agenda
- Participate in the meeting while it is active; YLD for meeting; drive the meeting towards the stated goals
```

### Message Buffering

#### Buffering Rules
1. **Human messages**: Never buffered, delivered immediately
2. **AI messages in meetings**: Buffered for up to 5 seconds
3. **Specific agent messages**: Buffer all messages until target responds

#### Buffer Timing
- Clock starts when first message arrives
- At YLD, continue waiting if time remains
- Human message in buffer triggers immediate delivery

### Meeting Lifecycle

#### Starting a Meeting
1. Meeting initiator agent executes: "Have a [type] meeting with [agents]"
2. Framework creates meeting ID
3. Framework sends invitations to specified agents
4. Framework waits for (required, if specified in metadata) agents to join (with exponential backoff)
6. When all (required, if specified in metadata) agents join, framework sends "Meeting started" to all participants and asks the initiator to start the meeting, e.g. "Meeting has started. AgentA, please start the meeting."
7. Initiating agent's meeting playbook begins execution

#### Joining a Meeting
1. Agent receives invitation message
2. Agent must have empty call stack to join; if not, it should send "REJECTED - busy" response
3. If agent cannot or does not want to join, it should send "REJECTED - [reason]" response
4. If agent can join and has a meeting playbook matching trigger, it sends "JOINED" response
5. Agent starts executing the meeting playbook

#### Leaving a Meeting
- Explicit: `Leave meeting` or `Leave meeting 123456`
- Implicit: Return from meeting playbook
- Framework notifies other participants: "[Agent] has left the meeting"

#### Ending a Meeting
- Explicit: `End meeting` or `End meeting 123456`
- Implicit: Last participant leaves
- Solo participant prompted: "End this meeting?"
- Framework sends "Meeting has ended" to all participants

### Dynamic Meeting Management

#### Adding Participants
```markdown
- Add TaxAgent to this meeting
```
Results in:
1. Invitation sent to TaxAgent
2. Current participants notified: "[Agent] invited TaxAgent. Waiting..."
3. When joined: "TaxAgent (agent id 12345678) has joined the meeting"

#### Idempotent Operations
- Adding same agent multiple times is a no-op
- Framework tracks pending invitations

---

## Implementation Details

### Core Classes

#### ExecutionState Enhancement
```python
class ExecutionState:
    # Existing fields...
    
    def get_current_meeting(self) -> Optional[str]:
        """Get meeting ID from top meeting playbook in call stack"""
        for frame in reversed(self.call_stack):
            if frame.is_meeting:
                return frame.meeting_id
        return None
    
    def get_say_target(self) -> str:
        """Determine default Say() target"""
        if meeting_id := self.get_current_meeting():
            return meeting_id
        return "human"
```

#### Meeting Manager
```python
class MeetingManager: # Mixin that will be added to ExecutionState
    def __init__(self):
        self.meetings: Dict[str, Meeting] = {}
        self.invitations: Dict[str, Set[str]] = {}  # agent_id -> meeting_ids
        
    async def create_meeting(
        self,
        initiator_id: str,
        meeting_type: str,
        invited_agents: List[str]
    ) -> str:
        """Create meeting and send invitations"""
        
    async def handle_join_request(
        self,
        agent_id: str,
        meeting_id: str
    ) -> bool:
        """Process agent joining meeting"""
        
    async def broadcast_to_meeting(
        self,
        meeting_id: str,
        message: Message,
        exclude_sender: bool = False
    ):
        """Send message to all meeting participants"""
```

#### Message Structure
```python
@dataclass
class Message:
    sender_id: str
    sender_type: str
    content: str
    timestamp: datetime
    meeting_id: Optional[str] = None
    message_type: str = "text"
```

### Interpreter Enhancements

#### Natural Language Processing
The interpreter must handle:
1. `Have a [type] meeting with [agents]` → `MeetingPlaybook(topic="Meeting topic", attendees=[agents])` topic and attendees must be specified either in MeetingPlaybook metadata or in the call instruction. Note that these named arguments are automatically added to playbook with meeting:true. 
2. `Add [agent] to this meeting` → `InviteToMeeting(["Accountant", "agent 23423432"])`
3. `Leave meeting [id]` → `return` from meeting playbook
4. `End meeting [id]` → `EndMeeting()` or `EndMeeting("meeting 123456")`

### Message Delivery System

#### Buffering Implementation
```python
class MessageBuffer:
    def __init__(self, timeout: float = 5.0):
        self.messages: List[Message] = []
        self.first_message_time: Optional[float] = None
        self.timeout = timeout
        
    def add_message(self, message: Message) -> bool:
        """Add message to buffer. Returns True if should flush."""
        self.messages.append(message)
        
        if self.first_message_time is None:
            self.first_message_time = time.time()
            
        # Flush immediately for human messages
        if message.sender_type == "Human":
            return True
            
        # Check timeout
        elapsed = time.time() - self.first_message_time
        return elapsed >= self.timeout
```

---

## Examples

### Simple Two-Agent Coordination
```markdown
# Flight Booking Agent

## Book Flight
### Triggers
- When user asks to book a flight

### Steps
- Inform user that you will help them book a flight
- Ask user for destination and dates
- Tell the user that you will check
- Ask PricingAgent to provide $pricing based on the destination and dates
- Present options to user

# Pricing Agent

## ProvidePricing($destination, $dates)
### Triggers
- When asked about pricing

### Steps
- Calculate dynamic pricing using $destination and $dates
- Return pricing
```

### Multi-Agent Meeting
```markdown
# Travel Coordinator

## Plan Trip
### Triggers
- When user asks to plan a trip

### Steps
- Tell the user that you will coordinate their trip planning
- Have a travel planning meeting to get best itinerary options
- Present itinerary options to user

## Travel Planning Meeting
meeting: true
required_attendees: [FlightAgent, HotelAgent]

### Steps
- Introduce yourself and the purpose of the meeting
- Share specific criteria for the trip
- Collaborate with the other agents in the meeting and drive the meeting towards finding the best itinerary options
- Thank the other agents for their contributions
- End meeting
- Return the itinerary options

# HotelAgent

## Planning meeting
meeting: true

### Steps
- Introduce yourself and what you can help with in this meeting
- While the meeting is active
  - When asked about hotel options
    - Ask RegionAgent if we support this region
    - If region is supported
      - Get hotel options for selected criteria
      - Share hotel options with the meeting
    - Otherwise
      - Say that unfortunately we don't support this region
  - When asked about amenities for a specific hotel
    - GetAmenities(hotel)
    - Reply to the meeting with the amenities
  - When you think you have something useful to say to the meeting
    - Say that to the meeting
```

### Dynamic Meeting Participation and Private Messages
```markdown
## Budget Review Meeting
meeting: true
required_attendees: [Supervisor, MarketingAgent]
optional_attendees: [AccountingAgent]

### Triggers
- When in budget review meeting

### Steps
- Introduce yourself
- Share current budget
- While the meeting is active
  - When you think costs may exceed budget
    - Say let's get accounting input
    - If AccountingAgent is not in the meeting
      - Add AccountingAgent to this meeting
    - Ask AccountingAgent for input providing full context
  - When you are unsure about something
    - Ask Supervisor agent priviately for guidance, providing full context
    - Think deeply about what the supervisor says
    - Share your thoughts with the meeting
  - ...
```

---
## Implementation Phases

### Phase 1: Foundation - Agent Identity & Enhanced State (Week 1)
**Goal**: Establish agent identity system and enhanced state tracking

**Tasks**:
1. **Agent ID System**
   - Implement sequential agent IDs starting at 1000
   - Ensure Human agent gets special ID "human"
   - Add agent registry to Program class
   - Update agent initialization

2. **State Tracking Enhancement**
   - Add last_message_target to ExecutionState (for Say() fallback)
   - Update state representation to include agents list
   - Prepare call stack for future meeting annotations

**Deliverables**:
- All agents have IDs
- State tracks last message target

### Phase 2: Enhanced Say() and YLD for Agent-to-Agent (Week 2)
**Goal**: Upgrade existing messaging with smarter routing and fallbacks

**Tasks**:
1. **Say() Enhancement**
   - Add optional target parameter to Say()
   - Implement target resolution (agent ID, agent type, "user"/"Human")
   - Add fallback logic: current context → last 1:1 target → Human
   - Track last_message_target on each Say()

2. **YLD Enhancement**
   - Change `YLD user` → `YLD for user` (last 1:1 human target with fallback to Human agent with id "human")
   - Add `YLD for agent <id>` and `YLD for <agent_type>`, including `YLD for Human`
   - Implement `YLD for agent` (last 1:1 non-human target, no fallback to human)
   - Keep existing functionality working

3. **Interpreter Updates**
   - Update interpreter to generate new Say() format
   - Handle "Ask X to do Y" patterns
 
**Deliverables**:
- Agent-to-agent messaging working
- Smart Say() fallbacks functional
- YLD supports agent sources

### Phase 3: Meeting Playbook Infrastructure (Week 3)
**Goal**: Add ability to recognize and parse meeting playbooks

**Tasks**:
1. **Meeting Metadata Support**
   - Parse `meeting: true` metadata in playbooks
   - Extract required_attendees and optional_attendees, if present
   - Flag meeting playbooks in AgentBuilder

2. **Meeting ID Generation**
   - Implement sequential meeting IDs starting at 100, instead of current UUIDs
   - Prepare for future meeting tracking

3. **Call Stack Enhancement**
   - Add is_meeting flag to CallStackFrame
   - Add meeting_id field to CallStackFrame
   - Update call stack display format to show `[meeting 123456]` for meeting frames

**Deliverables**:
- Meeting playbooks identified
- Meeting ID generation ready
- Call stack supports meeting annotation

### Phase 4: Basic Meeting Creation & Invitations (Week 4)
**Goal**: Implement meeting creation and invitation flow

**Tasks**:
1. **Meeting Manager**
   - Create MeetingManager class as a mixin for ExecutionState
   - Track meetings and invitations
   - Implement invitation sending via SendMessage

2. **Interpreter Updates**
   - Update interpreter prompt to process "Have a [type] meeting with [agents]" to generate MeetingPlaybook() calls with topic and attendees
   - Add topic/attendees as auto-parameters to meeting playbooks

3. **Invitation Flow**
   - Send invitation messages to agents
   - Asynchronously wait for agents to join (exponential backoff)
   - Implement JOINED/REJECTED response handling

4. **Join Request Handling**
   - Check call stack empty
   - If not empty, send "REJECTED - busy" response
   - If empty and agent has a meeting playbook matching trigger, send "JOINED" response and invoke meeting playbook
   - If empty and agent does not have a meeting playbook matching trigger, send "REJECTED - cannot handle this type of meeting. Here are the meeting types I can handle: [list of meeting types]" response with meeting types as the names of available meeting playbooks

**Deliverables**:
- Meetings can be created
- Invitations sent and tracked
- Basic accept/reject working

### Phase 5: Meeting Execution & Basic Lifecycle (Week 5)
**Goal**: Enable meeting playbook execution and basic lifecycle

**Tasks**:
1. **Meeting Start Coordination**
   - Wait for required attendees  
   - Send "Meeting started" notification
   - Prompt initiator: "Meeting has started. [Initiator agent], please start the meeting."

2. **Meeting Playbook Execution**
   - Trigger meeting playbooks on join
   - Add meeting context to call stack
   - Route Say() to meeting when in meeting context
   - Add intperpreter instructions to generate appropriate Say() calls - Say("meeting", "Accountant, what is the standarized deduction amount?") vs Say("Accountant", "What is the standarized deduction amount?"). Formar when Accountant is in the meeting and this is not a private message. Later when sending a private message or if Accountant is not in the meeting.

3. **Basic Lifecycle**
   - Implement leave (return from playbook)
   - Send "[Agent] has left" notifications
   - Handle last participant leaving

**Deliverables**:
- Meeting playbooks execute
- Basic join/leave working
- Say() routes to meetings

### Phase 6: Meeting Message Buffering & YLD (Week 6)
**Goal**: Implement sophisticated message handling for meetings

**Tasks**:
1. **Message Buffering**
   - Implement 5-second buffer for AI messages
   - Immediate delivery for Human messages
   - Buffer management per meeting

2. **YLD for Meetings**
   - Implement `YLD for meeting` (current meeting)
   - Implement `YLD for meeting 123456` (specific meeting)
   - Format buffered messages for LLM context

3. **State Updates**
   - Add meetings list to state representation
   - Show meeting participants
   - Update debugging output

**Deliverables**:
- Efficient message batching
- YLD works for meetings
- Complete state visibility

### Phase 7: Advanced Meeting Features (Week 7)
**Goal**: Add dynamic participation and advanced patterns

**Tasks**:
1. **Dynamic Participation**
   - Implement InviteToMeeting() function
   - Parse "Add [agent] to this meeting"
   - Handle late joining with context

2. **Meeting Management**
   - Implement EndMeeting() function
   - Solo participant prompting
   - Idempotent invitations

3. **Private Messages in Meetings**
   - Support explicit targeting while in meeting
   - Interpreter handles "privately ask" pattern
   - Maintain meeting context

**Deliverables**:
- Dynamic participation working
- Complete meeting management
- Private messaging supported

### Phase 8: Polish, Testing & Documentation (Week 8)
**Goal**: Production readiness

**Tasks**:
1. **Interpreter Excellence**
   - Refine context-aware translations
   - Handle edge cases gracefully
   - Optimize performance

2. **Comprehensive Testing**
   - Unit tests for each phase's features
   - Integration tests for full scenarios
   - Load testing for scale

3. **Documentation & Tools**
   - API documentation
   - Meeting pattern cookbook
   - Debug visualization
   - Migration guide

**Deliverables**:
- Production-ready system
- Comprehensive test suite
- Complete documentation
