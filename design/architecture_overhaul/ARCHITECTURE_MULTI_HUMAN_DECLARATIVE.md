# Multi-Human Support: Declarative Approach (RECOMMENDED)

## Executive Summary

This document proposes a **declarative syntax** for defining human agents directly in Playbooks programs, rather than requiring programmatic registration. This approach is more consistent with Playbooks' "Software 3.0" philosophy where programs are written in natural language with explicit declarations.

**Proposal**: Declare human agents in `.pb` files using `# AgentName:Human` syntax

**Benefits**:
- ✅ Declarative and self-documenting
- ✅ Explicit agent types (no magic defaults)
- ✅ Leverages existing agent syntax
- ✅ Makes target resolution unambiguous
- ✅ Enables compile-time validation
- ✅ Fits Playbooks philosophy perfectly

---

## 1. Current Problem (Recap)

**Current behavior**: One `HumanAgent` hardcoded with ID `"human"` in `Program.initialize()`

```python
# In program.py - HARDCODED
self.agents.append(
    HumanAgent(
        klass=HUMAN_AGENT_KLASS,
        agent_id="human",  # Magic default
        program=self,
        event_bus=self.event_bus,
    )
)
```

**Issues**:
- ❌ Implicit magic (human appears from nowhere)
- ❌ Only one human possible
- ❌ No way to specify human properties in program
- ❌ Not visible in .pb file
- ❌ Target resolution ambiguous with multiple humans

---

## 2. Proposed Declarative Syntax

### 2.1 Basic Human Agent Declaration

```markdown
# User:Human
```

**Behavior**:
- Declares a human agent with class name `User`
- Agent ID generated as `human_user` (consistent with other agent IDs)
- Available for message targeting: `Say("User", "Hello")`
- Compiler validates human agent references

### 2.2 Multiple Human Agents

```markdown
# Alice:Human

# Bob:Human

# Facilitator:AI
```

**Behavior**:
- Two human agents: `Alice` and `Bob`
- One AI agent: `Facilitator`
- Each human gets unique ID: `human_alice`, `human_bob`
- Clear targeting: `Say("Alice", "...")` vs `Say("Bob", "...")`

### 2.3 Human Agent with Metadata

```markdown
# Me:Human
metadata:
  name: Amol
  role: Programmer
  delivery_channel: streaming
  notification_preference: all
```

**Behavior**:
- Human agent named `Me` 
- Human-readable name: "Amol"
- Role metadata for context
- Delivery preferences specified declaratively
- Available in agent context during execution

### 2.4 Human Agent with Description

```markdown
# CustomerSupport:Human
"""
Customer support specialist who handles technical issues.
Prefers SMS notifications during business hours.
"""
metadata:
  real_name: Sarah Johnson
  phone: +1-555-0123
  delivery_channel: sms
  business_hours: 9am-5pm PST
```

**Behavior**:
- Description helps AI agents understand the human's role
- Metadata provides delivery configuration
- Can be used for routing decisions

---

## 3. Complete Example: Multi-Human Meeting

### 3.1 Team Meeting Scenario

```markdown
# ProjectManager:Human
"""
Project manager who coordinates team activities and makes final decisions.
"""
metadata:
  name: Alice Chen
  role: PM
  delivery_channel: streaming
  meeting_notifications: all

# Developer:Human
"""
Backend developer focused on API implementation.
"""
metadata:
  name: Bob Smith
  role: Backend Dev
  delivery_channel: sms
  meeting_notifications: targeted

# Designer:Human
"""
UI/UX designer responsible for user interface.
"""
metadata:
  name: Carol Williams  
  role: Designer
  delivery_channel: email
  meeting_notifications: none

# FacilitatorAgent:AI
"""
AI facilitator that runs team meetings and coordinates discussion.
"""

## TeamMeeting
meeting: true
required_attendees: [ProjectManager, Developer, Designer]

### Steps
- Welcome everyone to the meeting
- Ask ProjectManager to share project goals
- Ask Developer about technical feasibility
- Ask Designer about design considerations
- Summarize decisions and action items
```

**Execution behavior**:

```python
# At runtime:
# - ProjectManager (Alice): Gets real-time streaming updates
# - Developer (Bob): Gets SMS when mentioned ("Bob" or "Developer")
# - Designer (Carol): Gets email digest after meeting (notifications: none)

# When Facilitator says:
await facilitator.Say("meeting", "Welcome everyone!")

# Delivery:
# - Alice: Streams character-by-character
# - Bob: Buffered (not mentioned, targeted mode)
# - Carol: Ignored (notifications: none)

# When Facilitator says:
await facilitator.Say("meeting", "Bob, what's your take on the API design?")

# Delivery:
# - Alice: Streams (all notifications)
# - Bob: IMMEDIATE SMS (mentioned by name, overrides buffer)
# - Carol: Still ignored

# Direct message:
await facilitator.Say("ProjectManager", "Alice, can you approve the budget?")

# Delivery:
# - Alice only: Streams directly
# - Bob and Carol: Don't receive (not on channel)
```

---

## 4. Syntax Specification

### 4.1 Agent Type Annotation

```
# <AgentClassName>:<AgentType>

Where:
  AgentClassName: PascalCase identifier (e.g., User, Alice, CustomerSupport)
  AgentType: One of [Human, AI, MCP] (default: AI if not specified)
```

**Examples**:
```markdown
# Host              # AI agent (default)
# Host:AI           # AI agent (explicit)
# User:Human        # Human agent
# FileSystem:MCP    # MCP agent (future)
```

### 4.2 Human Agent Metadata Schema

```yaml
metadata:
  # Required fields
  name: string          # Human-readable name (e.g., "Alice Chen")
  
  # Optional delivery configuration
  delivery_channel: streaming | sms | email | webhook | custom
  delivery_handler: string  # Custom handler ID (if channel=custom)
  
  # Optional streaming configuration
  streaming_enabled: bool   # Enable/disable streaming (default: true)
  streaming_chunk_size: int # Characters per chunk (default: 1)
  
  # Optional buffering configuration
  buffer_messages: bool     # Accumulate messages (default: false)
  buffer_timeout: float     # Seconds to accumulate (default: 5.0)
  
  # Optional meeting configuration
  meeting_notifications: all | targeted | none  # (default: targeted)
  
  # Optional contact information
  phone: string
  email: string
  
  # Optional context
  role: string              # Role description
  timezone: string          # For scheduling
  business_hours: string    # For notifications
  
  # Optional custom metadata (any valid YAML)
  <custom_key>: <custom_value>
```

### 4.3 Metadata Validation Rules

**At compile time**:
1. Validate required fields (`name` must be present)
2. Validate enum values (`delivery_channel`, `meeting_notifications`)
3. Validate data types (bool, int, float, string)
4. Warn on unknown fields (but don't fail - allow extensibility)

**At runtime**:
1. Merge metadata with defaults
2. Create `DeliveryPreferences` from metadata
3. Register human with preferences

---

## 5. Compilation Pipeline Changes

### 5.1 Current Pipeline (AI Agents Only)

```
.pb file (Markdown)
  ↓
Compiler (LLM preprocessing)
  ↓
.pbasm file (Assembly)
  ↓
markdown_to_ast() parsing
  ↓
AgentBuilder.create_agent_classes_from_ast()
  ↓
Creates AIAgent subclasses only
  ↓
Program.initialize()
  ↓
Hardcoded HumanAgent creation
```

### 5.2 Proposed Pipeline (Multi-Type Agents)

```
.pb file (Markdown with :Human annotations)
  ↓
Compiler (LLM preprocessing)
  ↓
.pbasm file (Assembly with agent types preserved)
  ↓
markdown_to_ast() parsing
  ├─> Parse agent type annotations (:Human, :AI, :MCP)
  └─> Extract metadata per agent
  ↓
AgentBuilder.create_agent_classes_from_ast()
  ├─> Create AIAgent subclasses (for :AI)
  ├─> Create HumanAgent subclasses (for :Human)  # NEW
  └─> Create MCPAgent subclasses (for :MCP)      # FUTURE
  ↓
Program.initialize()
  ├─> Instantiate AI agents (as before)
  ├─> Instantiate Human agents (NEW - from declarations)
  └─> NO hardcoded HumanAgent creation
```

---

## 6. Implementation Details

### 6.1 AST Parsing Enhancement

**Location**: `utils/markdown_to_ast.py`

```python
def parse_h1_header(header_text: str) -> dict:
    """Parse H1 header to extract agent name and type.
    
    Examples:
        "# Host" → {"name": "Host", "type": "AI"}
        "# Host:AI" → {"name": "Host", "type": "AI"}
        "# User:Human" → {"name": "User", "type": "Human"}
        "# FileSystem:MCP" → {"name": "FileSystem", "type": "MCP"}
    """
    # Remove leading # and whitespace
    clean_header = header_text.lstrip('#').strip()
    
    # Check for type annotation
    if ':' in clean_header:
        name, agent_type = clean_header.split(':', 1)
        name = name.strip()
        agent_type = agent_type.strip()
        
        # Validate agent type
        valid_types = ['AI', 'Human', 'MCP']
        if agent_type not in valid_types:
            raise ValueError(f"Invalid agent type: {agent_type}. Must be one of {valid_types}")
        
        return {
            "name": name,
            "type": agent_type
        }
    else:
        # No type annotation - default to AI
        return {
            "name": clean_header,
            "type": "AI"
        }

# In markdown_to_ast():
def markdown_to_ast(content: str, source_file_path: str = None) -> dict:
    """Parse markdown content into AST."""
    # ... existing parsing ...
    
    # Parse H1 headers with type annotations
    for h1 in h1_sections:
        header_info = parse_h1_header(h1.heading_text)
        
        agent_ast = {
            "name": header_info["name"],
            "type": header_info["type"],  # NEW
            "description": h1.description,
            "metadata": parse_metadata(h1.metadata_block),  # NEW
            "playbooks": parse_playbooks(h1.h2_sections),
            # ...
        }
        ast.append(agent_ast)
    
    return ast
```

### 6.2 AgentBuilder Enhancement

**Location**: `agents/agent_builder.py`

```python
class AgentBuilder:
    @classmethod
    def create_agent_classes_from_ast(cls, ast: dict) -> Dict[str, Type[BaseAgent]]:
        """Create agent classes from AST.
        
        Now supports multiple agent types: AI, Human, MCP
        """
        agent_classes = {}
        
        for agent_ast in ast:
            agent_type = agent_ast.get("type", "AI")
            
            if agent_type == "AI":
                # Existing logic for AI agents
                agent_class = cls._create_ai_agent_class(agent_ast)
            
            elif agent_type == "Human":
                # NEW: Create HumanAgent subclass
                agent_class = cls._create_human_agent_class(agent_ast)
            
            elif agent_type == "MCP":
                # FUTURE: Create MCPAgent subclass
                agent_class = cls._create_mcp_agent_class(agent_ast)
            
            else:
                raise ValueError(f"Unknown agent type: {agent_type}")
            
            agent_classes[agent_ast["name"]] = agent_class
        
        return agent_classes
    
    @classmethod
    def _create_human_agent_class(cls, agent_ast: dict) -> Type[HumanAgent]:
        """Create a HumanAgent subclass from AST.
        
        Example AST:
        {
            "name": "Alice",
            "type": "Human",
            "description": "Project manager...",
            "metadata": {
                "name": "Alice Chen",
                "role": "PM",
                "delivery_channel": "streaming",
                ...
            }
        }
        """
        agent_name = agent_ast["name"]
        agent_description = agent_ast.get("description", "")
        agent_metadata = agent_ast.get("metadata", {})
        
        # Extract delivery preferences from metadata
        delivery_prefs = cls._extract_delivery_preferences(agent_metadata)
        
        # Create HumanAgent subclass dynamically
        class DynamicHumanAgent(HumanAgent):
            klass = agent_name
            description = agent_description
            metadata = agent_metadata
            delivery_preferences = delivery_prefs
            
            def __init__(self, event_bus, agent_id, program):
                super().__init__(
                    klass=self.klass,
                    agent_id=agent_id,
                    name=agent_metadata.get("name", agent_name),
                    delivery_preferences=self.delivery_preferences,
                    program=program,
                    event_bus=event_bus
                )
        
        DynamicHumanAgent.__name__ = agent_name
        return DynamicHumanAgent
    
    @classmethod
    def _extract_delivery_preferences(cls, metadata: dict) -> DeliveryPreferences:
        """Extract DeliveryPreferences from metadata dict."""
        return DeliveryPreferences(
            channel=metadata.get("delivery_channel", "streaming"),
            streaming_enabled=metadata.get("streaming_enabled", True),
            streaming_chunk_size=metadata.get("streaming_chunk_size", 1),
            buffer_messages=metadata.get("buffer_messages", False),
            buffer_timeout=metadata.get("buffer_timeout", 5.0),
            meeting_notifications=metadata.get("meeting_notifications", "targeted"),
            custom_handler=metadata.get("delivery_handler"),
        )
```

### 6.3 Program Initialization Enhancement

**Location**: `program.py`

```python
class Program:
    async def initialize(self):
        """Initialize agents from compiled program.
        
        Now creates agents based on declarations in .pb file.
        No hardcoded HumanAgent creation.
        """
        # Create agent instances based on should_create_instance_at_start()
        # This includes both AI and Human agents
        self.agents = [
            await self.create_agent(klass)
            for klass in self.agent_klasses.values()
            if klass.should_create_instance_at_start()
        ]
        
        # Validate: If program uses human references but no humans declared
        if self._program_references_humans() and not self._has_any_humans():
            raise ValueError(
                "Program references 'human' or 'user' but no Human agents declared. "
                "Add a Human agent declaration like:\n\n"
                "  # User:Human\n"
            )
        
        # Register all agents
        for agent in self.agents:
            if agent.klass not in self.agents_by_klass:
                self.agents_by_klass[agent.klass] = []
            self.agents_by_klass[agent.klass].append(agent)
            self.agents_by_id[agent.id] = agent
            agent.program = self
        
        self.initialized = True
    
    def _program_references_humans(self) -> bool:
        """Check if program references 'human' or 'user' in Say() calls."""
        # Could do AST analysis or runtime detection
        # For now, return False (require explicit declaration)
        return False
    
    def _has_any_humans(self) -> bool:
        """Check if any human agents are declared."""
        return any(
            isinstance(agent, HumanAgent)
            for agent in self.agents
        )
```

### 6.4 HumanAgent Base Class Enhancement

**Location**: `agents/human_agent.py`

```python
class HumanAgent(BaseAgent):
    # Remove class-level attributes (now dynamic)
    # klass = HUMAN_AGENT_KLASS  # REMOVED
    # description = "A human agent."  # REMOVED
    # metadata = {}  # REMOVED
    
    def __init__(
        self,
        klass: str,  # Now required (from declaration)
        event_bus: EventBus,
        agent_id: str,
        name: str,  # Human-readable name
        delivery_preferences: DeliveryPreferences,
        program: "Program",
        **kwargs
    ):
        super().__init__(agent_id=agent_id, program=program, **kwargs)
        self.klass = klass  # Instance attribute
        self.id = agent_id
        self.name = name
        self.delivery_preferences = delivery_preferences
        
        # HumanAgent has minimal state (no execution)
        self.state = ExecutionState(event_bus, klass, agent_id)
    
    async def begin(self):
        # Human agent does not process messages
        pass
    
    def __str__(self):
        return f"HumanAgent({self.name}, {self.id})"
    
    def __repr__(self):
        return f"HumanAgent({self.name}, {self.klass}, {self.id})"
```

---

## 7. Target Resolution with Declared Humans

### 7.1 Unambiguous Resolution

**Before (AMBIGUOUS)**:
```python
# Say("user", "Hello")  # Which user???
# Multiple humans exist but all called "user"
```

**After (CLEAR)**:
```python
# Declaration in .pb:
# Alice:Human
# Bob:Human

# Usage in steps:
await Say("Alice", "Hello Alice!")  # Clear: targets Alice
await Say("Bob", "Hello Bob!")      # Clear: targets Bob

# Also works with lowercase (case-insensitive):
await Say("alice", "Hi")            # Resolves to Alice

# Or with human ID:
await Say("human_alice", "Hey")     # Explicit ID
```

### 7.2 Enhanced resolve_target()

```python
def resolve_target(self, target: str = None, allow_fallback: bool = True) -> str:
    """Resolve target to agent ID.
    
    With declared humans, resolution is unambiguous:
    - "Alice" → looks up HumanAgent with klass="Alice"
    - "Bob" → looks up HumanAgent with klass="Bob"
    - "Host" → looks up AIAgent with klass="Host"
    """
    if target is not None:
        target = target.strip()
        
        # 1. Check if it's an agent class name (Human or AI)
        for agent in self.program.agents:
            if agent.klass.lower() == target.lower():
                return agent.id
        
        # 2. Check if it's a spec format
        if SpecUtils.is_agent_spec(target):
            return SpecUtils.extract_agent_id(target)
        
        # 3. Check if it's a raw agent ID
        if target in self.program.agents_by_id:
            return target
        
        # 4. Not found
        if allow_fallback and self._has_single_human():
            # Only fallback if there's exactly ONE human
            return self._get_single_human_id()
        
        raise ValueError(
            f"Target '{target}' not found. "
            f"Available agents: {', '.join(a.klass for a in self.program.agents)}"
        )
    
    # No target specified
    if not allow_fallback:
        return None
    
    # Fallback logic: current meeting → single human → error
    if meeting_id := self.state.get_current_meeting():
        return f"meeting {meeting_id}"
    
    if self._has_single_human():
        return self._get_single_human_id()
    
    raise ValueError(
        "No target specified and cannot infer. "
        "Please specify target explicitly."
    )
```

### 7.3 Backward Compatibility Mode

For existing programs that use "human" or "user":

**Option 1: Single default human** (transitional)
```markdown
# User:Human
# (allows "Say('user', ...)" to work)
```

**Option 2: Compilation error** (strict)
```
Error: Reference to 'human' or 'user' without Human agent declaration.

Add a Human agent to your program:
  # User:Human

Or specify the human's name explicitly:
  # Alice:Human
```

---

## 8. Migration Path

### 8.1 Phase 1: Add Declarative Support (Non-Breaking)

**Tasks**:
1. Add agent type annotation parsing (`:Human`, `:AI`)
2. Add metadata extraction for human agents
3. Create `_create_human_agent_class()` in AgentBuilder
4. Keep hardcoded HumanAgent creation as fallback
5. If no `:Human` declared, create default "human" (backward compatible)

**Result**: Existing programs continue working

---

### 8.2 Phase 2: Deprecation Warnings

**Tasks**:
1. Emit warning if program uses "human"/"user" without declaration
2. Add migration guide to error messages
3. Update documentation with new syntax
4. Update all examples to use declarative syntax

**Result**: Users are warned but programs still work

---

### 8.3 Phase 3: Breaking Change (Major Version)

**Tasks**:
1. Remove hardcoded HumanAgent creation
2. Require explicit `:Human` declaration
3. Error if "human"/"user" referenced without declaration
4. Update all examples and tests

**Result**: Clean, consistent declarative syntax

---

## 9. Complete Working Example

### 9.1 Customer Support System

```markdown
# Customer:Human
"""
Customer seeking technical support for their issue.
"""
metadata:
  name: John Doe
  contact_method: chat
  delivery_channel: streaming
  meeting_notifications: all

# SupportAgent:Human
"""
Technical support specialist who resolves customer issues.
Available via SMS during business hours.
"""
metadata:
  name: Sarah Johnson
  role: Support Specialist
  phone: +1-555-0123
  delivery_channel: sms
  meeting_notifications: targeted
  business_hours: 9am-5pm PST

# SupportCoordinator:AI
"""
AI coordinator that facilitates support conversations and escalates when needed.
"""

## HandleSupportRequest
### Steps
- Greet Customer and ask about their issue
- Analyze the issue complexity
- If issue is simple
  - Provide solution directly
  - Ask Customer if issue is resolved
- Otherwise
  - Start support session with Customer and SupportAgent
  - Facilitate troubleshooting discussion
  - Document solution
- Thank Customer for their patience

## SupportSession
meeting: true
required_attendees: [Customer, SupportAgent]

### Steps
- Welcome both parties to the support session
- Ask Customer to describe the issue in detail
- Ask SupportAgent for diagnostic questions
- Relay questions to Customer
- Get answers from Customer
- Ask SupportAgent for solution
- Confirm solution works with Customer
- Summarize resolution for records
```

**Execution behavior**:

```python
# Runtime behavior:

# 1. SupportCoordinator greets customer
await coordinator.Say("Customer", "Hello! How can I help you today?")
# → Customer receives real-time streaming (chat interface)

# 2. Customer describes issue (via chat)
customer_response = await coordinator.WaitForMessage("Customer")
# → Coordinator receives message

# 3. Coordinator analyzes and decides to escalate
await coordinator.execute_playbook("SupportSession", {
    "required_attendees": ["Customer", "SupportAgent"]
})
# → Meeting invitation sent to both humans

# 4. In meeting - Coordinator asks question
await coordinator.Say("meeting", "Sarah, what diagnostics should we run?")
# → Customer: Streams immediately (meeting_notifications: all)
# → SupportAgent: IMMEDIATE SMS (mentioned by name, targeted mode)

# 5. SupportAgent responds via SMS
agent_response = await coordinator.WaitForMessage("meeting")
# → Receives SMS response from SupportAgent

# 6. Coordinator relays to customer
await coordinator.Say("meeting", "John, can you try running this command?")
# → Customer: Streams immediately (mentioned, in meeting)
# → SupportAgent: Buffered (not mentioned, targeted mode)

# 7. Resolution confirmed
await coordinator.Say("Customer", "Great! Your issue is resolved.")
# → Customer receives final message via streaming
# → Meeting ends
# → SupportAgent receives SMS summary if configured
```

---

## 10. Advantages of Declarative Approach

### 10.1 vs. Programmatic Registration

**Programmatic** (from ARCHITECTURE_MULTI_HUMAN.md):
```python
# In Python application code
program = Program(...)
alice = program.register_human(
    "human_alice", "Alice",
    DeliveryPreferences(channel="streaming")
)
```

**Declarative** (this proposal):
```markdown
# In .pb file
# Alice:Human
metadata:
  name: Alice Chen
  delivery_channel: streaming
```

**Advantages**:
1. ✅ **Self-documenting**: Humans visible in playbook file
2. ✅ **Declarative**: Fits Playbooks philosophy
3. ✅ **Compile-time validation**: Catch errors early
4. ✅ **No application code needed**: Pure playbook definition
5. ✅ **Portable**: Playbook file is complete specification
6. ✅ **Versionable**: Human config in same file as logic
7. ✅ **LLM-friendly**: Natural language declarations

### 10.2 Consistency with Framework Design

Playbooks framework principles:
- "Software 3.0" - natural language programming
- Declarative over imperative
- Everything in the .pb file
- LLMs can understand and modify
- Compile once, run anywhere

**Declarative humans align perfectly**:
```markdown
# ✅ Agents declared in .pb
# ✅ Playbooks declared in .pb
# ✅ Metadata declared in .pb
# ✅ Triggers declared in .pb
# ✅ Humans declared in .pb  ← NEW, consistent!
```

### 10.3 Developer Experience

**Writing a program**:
```markdown
# 1. Declare agents (AI and Human)
# Host:AI
# User:Human

# 2. Define playbooks
## Greet
### Steps
- Say("User", "Welcome!")  # Clear target

# 3. Run program
# No setup code needed!
```

**vs. programmatic**:
```python
# 1. Load program
program = Program(event_bus, program_paths=["example.pb"])

# 2. Register humans (setup code)
user = program.register_human("human_user", "User", prefs)

# 3. Initialize and run
await program.initialize()
await program.run_till_exit()
```

Declarative is **simpler and clearer**.

---

## 11. Open Questions and Decisions

### 11.1 Should HumanAgent Instantiation be Eager or Lazy?

**Option A: Eager** (create all declared humans at initialization)
```python
# All humans created in Program.initialize()
# Available immediately
```
- ✅ Simple
- ✅ Predictable
- ❌ Creates humans even if never used

**Option B: Lazy** (create humans on first reference)
```python
# Humans created when first mentioned in Say() or meeting
# Similar to how other agents work
```
- ✅ Efficient (only create what's needed)
- ✅ Consistent with agent spawning
- ❌ More complex
- ❌ Might surprise users

**Recommendation**: **Eager** - humans should be created upfront since they're explicitly declared and likely to be used.

### 11.2 Default Agent Type if No Annotation

**Option A: AI (current behavior)**
```markdown
# Host  ← Defaults to AI
```

**Option B: Require explicit annotation**
```markdown
# Host  ← ERROR: Must specify :AI or :Human
```

**Recommendation**: **Option A (AI default)** - backward compatible, 99% of agents are AI.

### 11.3 Can Humans Have Playbooks?

**Scenario**: Human wants to define custom behavior

```markdown
# Developer:Human
metadata:
  name: Bob

## OnMeetingInvite($meeting_id)
### Steps
- If meeting is urgent
  - Accept immediately
- Otherwise
  - Check calendar
  - If available, accept
  - Otherwise, decline
```

**Question**: Should humans be able to define playbooks?

**Recommendation**: **No, not initially**. Humans don't execute playbooks autonomously. If needed, create an AI agent that represents the human's logic.

### 11.4 Authentication and Session Mapping

**Question**: How do we map authenticated sessions to declared humans?

**Answer**: Application layer responsibility:

```python
# Application code (e.g., web server)
@app.route("/api/message")
async def send_message(request):
    # 1. Authenticate user
    auth_token = request.headers["Authorization"]
    user_id = validate_token(auth_token)
    
    # 2. Map to declared human
    # User "alice@company.com" maps to "Alice:Human" in playbook
    human_class_name = get_human_class_for_user(user_id)  # → "Alice"
    
    # 3. Find agent
    human_agent = program.get_agent_by_klass(human_class_name)
    
    # 4. Send message on their behalf
    await human_agent.Say(request.json["target"], request.json["message"])
```

---

## 12. Comparison: Programmatic vs. Declarative

| Aspect | Programmatic API | Declarative Syntax |
|--------|------------------|-------------------|
| **Definition location** | Python application code | .pb playbook file |
| **Visibility** | Hidden in app code | Visible in playbook |
| **Portability** | Requires app setup | Self-contained in .pb |
| **Validation** | Runtime only | Compile-time + runtime |
| **LLM comprehension** | Difficult | Natural language |
| **Versionability** | Separate from playbook | Same file as logic |
| **Consistency** | Breaks framework patterns | Aligns with framework |
| **Setup complexity** | Requires registration code | Zero setup code |
| **Target resolution** | Ambiguous without docs | Clear from declarations |
| **Error messages** | Runtime errors | Compile-time errors |

**Verdict**: **Declarative is superior** for Playbooks framework.

---

## 13. Implementation Checklist

### Phase 1: Syntax Support (2 weeks)
- [ ] Add `:Human` type annotation parsing in markdown_to_ast
- [ ] Extract metadata for human agents
- [ ] Create `_create_human_agent_class()` in AgentBuilder
- [ ] Update HumanAgent base class for declarative construction
- [ ] Keep hardcoded fallback for backward compatibility
- [ ] Add tests for declarative human syntax

### Phase 2: Delivery Preferences (1 week)
- [ ] Implement DeliveryPreferences class
- [ ] Parse delivery preferences from metadata
- [ ] Wire up preferences in HumanAgent initialization
- [ ] Add tests for different delivery modes

### Phase 3: Target Resolution (1 week)
- [ ] Update resolve_target() for declared humans
- [ ] Add validation for unknown targets
- [ ] Improve error messages with suggestions
- [ ] Add tests for target resolution

### Phase 4: Validation (1 week)
- [ ] Add compile-time validation for human references
- [ ] Validate metadata schema
- [ ] Check for duplicate human names
- [ ] Add helpful error messages

### Phase 5: Documentation (1 week)
- [ ] Update syntax documentation
- [ ] Add examples with multiple humans
- [ ] Migration guide for existing code
- [ ] Tutorial on multi-human meetings

### Phase 6: Breaking Change (1 week)
- [ ] Remove hardcoded HumanAgent creation
- [ ] Require explicit `:Human` declarations
- [ ] Update all examples
- [ ] Release notes and migration guide

**Total: 6-7 weeks**

---

## 14. Conclusion

The **declarative approach** for multi-human support is **strongly recommended** over programmatic registration because:

1. ✅ **Aligns with Playbooks philosophy**: Natural language, declarative, self-documenting
2. ✅ **Simpler for users**: No setup code required, everything in .pb file
3. ✅ **Better error messages**: Compile-time validation catches issues early
4. ✅ **More maintainable**: Humans and their config are version-controlled with logic
5. ✅ **LLM-friendly**: Natural language declarations that LLMs can understand and generate
6. ✅ **Unambiguous targeting**: Clear agent names from declarations

The syntax is elegant and consistent:
```markdown
# Alice:Human          ← Human agent
# Bob:Human            ← Another human
# Facilitator:AI       ← AI agent (explicit)
# Host                 ← AI agent (default)
```

This approach makes Playbooks programs more **complete, portable, and understandable** while enabling rich multi-human scenarios like team meetings, customer support, and collaborative workflows.

**Next steps**:
1. Implement syntax parsing and validation
2. Update HumanAgent for declarative construction
3. Add delivery preferences system
4. Provide migration path for existing code
5. Document and release!

