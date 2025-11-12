# Migration from DeepAgents to Playbooks

This document details how the original DeepAgents implementation maps to the Playbooks version.

## Code Size Comparison

| Component | Original (Python) | Playbooks | Reduction |
|-----------|------------------|-----------|-----------|
| Main Agent Logic | ~1,200 lines | ~150 lines | 87% |
| Filesystem Tools | ~700 lines | ~350 lines | 50% |
| Subagent System | ~500 lines | ~40 lines | 92% |
| Shell Tools | ~200 lines | ~80 lines | 60% |
| Web Tools | ~200 lines | ~150 lines | 25% |
| CLI/Execution | ~500 lines | ~0 lines | 100% |
| **TOTAL** | **~3,300 lines** | **~770 lines** | **77%** |

The MCP server code is more verbose because it includes explicit error handling and documentation, but the agent logic itself is dramatically simpler.

## Architecture Mapping

### 1. Planning & Task Decomposition

**Original (DeepAgents):**
```python
# libs/deepagents/graph.py
from langchain.agents.middleware import TodoListMiddleware

middleware = [
    TodoListMiddleware(),
    # ... other middleware
]

agent = create_agent(
    model,
    system_prompt=system_prompt,
    middleware=middleware
)
```

**Playbooks:**
```markdown
## HandleComplexTask($task_description)
### Steps
- Analyze the $task_description to identify subtasks
- If task involves heavy research
  - Delegate research subtasks to ResearchAgent in parallel
  - Wait for research results
- Execute the task using available tools
- Return summary of accomplishments
```

**Why Better:** Natural language planning is more flexible and readable. No need for explicit todo management middleware - just describe the workflow.

---

### 2. Filesystem Operations

**Original (DeepAgents):**
```python
# libs/deepagents/middleware/filesystem.py (700+ lines)
class FilesystemMiddleware(AgentMiddleware):
    def __init__(self, backend: BackendProtocol):
        self.backend = backend
        self.tools = _get_filesystem_tools(backend)
    
    def wrap_model_call(self, request, handler):
        # Inject filesystem system prompt
        request.system_prompt += FILESYSTEM_SYSTEM_PROMPT
        return handler(request)
    
    def wrap_tool_call(self, request, handler):
        # Handle large tool results
        result = handler(request)
        if len(result.content) > self.token_limit:
            # Save to file and return reference
            ...
        return result

# Plus backend implementations:
# - StateBackend (~150 lines)
# - FilesystemBackend (~480 lines)
# - CompositeBackend (~100 lines)
```

**Playbooks:**
```markdown
# FilesystemAgent
Agent providing file system operations through MCP integration.

remote:
  type: mcp
  transport: streamable-http
  url: http://127.0.0.1:8000/mcp
```

With MCP server (~350 lines):
```python
@mcp.tool
def read_file(file_path: str, offset: int = 0, limit: int = 500):
    """Read file content with line numbers."""
    # Implementation
    return {"content": "...", "total_lines": 100}
```

**Why Better:** 
- Separation of concerns: MCP server handles deterministic logic
- Remote agents can be reused across different Playbooks programs
- Simpler mental model: agent calls tools, tools return results
- No complex middleware chain to debug

---

### 3. Subagent System

**Original (DeepAgents):**
```python
# libs/deepagents/middleware/subagents.py (500+ lines)
class SubAgentMiddleware(AgentMiddleware):
    def __init__(
        self,
        default_model,
        default_tools,
        default_middleware,
        subagents,
        general_purpose_agent=True
    ):
        self.subagent_graphs = {}
        
        # Create general-purpose subagent
        if general_purpose_agent:
            self.subagent_graphs["general-purpose"] = create_agent(
                default_model,
                tools=default_tools,
                middleware=default_middleware
            )
        
        # Create custom subagents
        for agent_spec in subagents:
            if "runnable" in agent_spec:
                self.subagent_graphs[agent_spec["name"]] = agent_spec["runnable"]
            else:
                self.subagent_graphs[agent_spec["name"]] = create_agent(
                    agent_spec.get("model", default_model),
                    system_prompt=agent_spec["system_prompt"],
                    tools=agent_spec.get("tools", []),
                    middleware=agent_spec.get("middleware", [])
                )
        
        # Create task tool that routes to subagents
        self.tools = [_create_task_tool(self.subagent_graphs)]

# Usage:
research_subagent = {
    "name": "research-agent",
    "description": "Used to research questions",
    "system_prompt": "You are a researcher...",
    "tools": [internet_search],
}

agent = create_deep_agent(
    subagents=[research_subagent]
)
```

**Playbooks:**
```markdown
# CodingAgent
Main coding assistant.

## HandleComplexTask($task)
### Steps
- If task requires research
  - Delegate to ResearchAgent for focused investigation
- Execute implementation

---

# ResearchAgent
Specialized research agent.

## ResearchTopic($topic)
### Steps
- Search web for information
- Synthesize findings
- Return comprehensive report
```

**Why Better:**
- Native multi-agent support without middleware
- Simple agent-to-agent calls with natural syntax
- No complex routing logic or graph management
- Subagents defined in same file or separate `.pb` files

---

### 4. Web Research Tools

**Original (DeepAgents):**
```python
# libs/deepagents-cli/deepagents_cli/tools.py
def web_search(query, max_results=5, topic="general", include_raw_content=False):
    """Search the web using Tavily..."""
    if tavily_client is None:
        return {"error": "Tavily API key not configured"}
    
    try:
        search_docs = tavily_client.search(
            query,
            max_results=max_results,
            include_raw_content=include_raw_content,
            topic=topic
        )
        return search_docs
    except Exception as e:
        return {"error": f"Web search error: {e}"}

# Registration:
tools = [web_search, fetch_url, http_request]
agent = create_deep_agent(tools=tools)
```

**Playbooks:**
```python
# web_tools_mcp.py
@mcp.tool
def web_search(query: str, max_results: int = 5, ...):
    """Search the web using Tavily."""
    # Implementation
    return search_docs
```

```markdown
# WebAgent
remote:
  type: mcp
  transport: streamable-http
  url: http://127.0.0.1:8001/mcp
```

**Why Better:**
- MCP servers can be shared across projects
- Tools are self-documenting with FastMCP
- Easy to test tools independently
- Version and deploy tools separately from agent logic

---

### 5. Human-in-the-Loop

**Original (DeepAgents):**
```python
# libs/deepagents-cli/deepagents_cli/agent.py
def format_write_file_description(tool_call: dict) -> str:
    args = tool_call.get("args", {})
    file_path = args.get("file_path")
    content = args.get("content")
    action = "Overwrite" if os.path.exists(file_path) else "Create"
    return f"File: {file_path}\nAction: {action} file\nLines: {len(content.splitlines())}"

write_file_interrupt_config = {
    "allowed_decisions": ["approve", "reject"],
    "description": lambda tool_call, state, runtime: format_write_file_description(tool_call)
}

agent = create_deep_agent(
    interrupt_on={
        "write_file": write_file_interrupt_config,
        "edit_file": edit_file_interrupt_config,
        "shell": shell_interrupt_config,
        # ... more configs
    }
)

# Execution loop handles interrupts:
while True:
    result = agent.invoke(state)
    if result.get("interrupt"):
        # Prompt user for approval
        decision = prompt_user(result["interrupt_data"])
        if decision == "approve":
            state = agent.resume(state)
        else:
            # Handle rejection
```

**Playbooks:**
```markdown
# Playbooks has built-in approval mechanisms
# Configure via playbooks.toml:

[approval]
tools = ["write_file", "edit_file", "shell"]
mode = "interactive"  # or "auto"
```

Agent automatically pauses for approval and resumes based on user input.

**Why Better:**
- Built into framework, no custom middleware needed
- Consistent approval UI across all agents
- Simpler configuration

---

### 6. Memory Management

**Original (DeepAgents):**
```python
# Complex backend system with multiple implementations
class CompositeBackend:
    def __init__(self, default, routes):
        self.default = default
        self.routes = routes  # {"/memories/": StoreBackend(), ...}
    
    def read(self, path):
        backend = self._get_backend_for_path(path)
        return backend.read(path)

# Memory middleware
class AgentMemoryMiddleware(AgentMiddleware):
    def __init__(self, backend, memory_path="/memories/"):
        self.backend = backend
        self.memory_path = memory_path
    
    def wrap_model_call(self, request, handler):
        # Inject memory context
        memories = self.backend.ls(self.memory_path)
        request.system_prompt += f"\n\nMemories: {memories}"
        return handler(request)

# Setup:
agent_dir = Path.home() / ".deepagents" / agent_id
long_term_backend = FilesystemBackend(root_dir=agent_dir, virtual_mode=True)
backend = CompositeBackend(
    default=FilesystemBackend(),
    routes={"/memories/": long_term_backend}
)
agent = create_deep_agent(backend=backend, middleware=[AgentMemoryMiddleware(...)])
```

**Playbooks:**
```markdown
## Main
### Steps
- Load $context from /memories/context.md if it exists
- Welcome user with context-aware greeting
- While conversing
  - When user shares important information
    - Save to /memories/ using FilesystemAgent
  - Use saved context to inform responses
```

Or use Playbooks Artifacts for session memory:
```markdown
## SaveToMemory($key, $value)
### Steps
- Create artifact with $key containing $value
- Confirm saved to user
```

**Why Better:**
- Explicit memory operations in natural language
- No hidden middleware injecting context
- Developer chooses when/how to use memory
- Built-in Artifacts feature for session state

---

### 7. CLI and Execution

**Original (DeepAgents):**
```python
# libs/deepagents-cli/deepagents_cli/main.py (200+ lines)
async def simple_cli(agent, assistant_id, session_state, baseline_tokens):
    console.print(DEEP_AGENTS_ASCII)
    session = create_prompt_session(assistant_id, session_state)
    token_tracker = TokenTracker()
    
    while True:
        try:
            user_input = await session.prompt_async()
            # Handle slash commands
            if user_input.startswith("/"):
                result = handle_command(user_input, agent, token_tracker)
                # ...
            # Handle bash commands
            if user_input.startswith("!"):
                execute_bash_command(user_input)
                # ...
            # Execute agent
            await execute_task(user_input, agent, assistant_id, session_state, token_tracker)
        except KeyboardInterrupt:
            break

# libs/deepagents-cli/deepagents_cli/execution.py (150+ lines)
async def execute_task(user_input, agent, assistant_id, session_state, token_tracker):
    # Complex execution with streaming, interrupts, token tracking, etc.
    async for chunk in agent.astream(...):
        # Handle AIMessage, ToolCall, etc.
        # Update UI
        # Track tokens
        # Handle interrupts
```

**Playbooks:**
```bash
# Just run it!
playbooks run deepagent.pb
```

All CLI features built into Playbooks framework:
- Interactive prompt with history
- Streaming output
- Token tracking
- Interrupt handling
- Session management
- Debugging tools

**Why Better:**
- Zero boilerplate for CLI
- Consistent experience across all Playbooks programs
- Built-in playground for development
- VSCode debugging support

---

## Benefits Summary

### 1. **Simplicity**
- 77% less code overall
- Natural language is more intuitive than Python orchestration
- Fewer abstractions to learn

### 2. **Readability**
- Business stakeholders can read `.pb` files
- Agent behavior is self-documenting
- No need to trace through middleware chains

### 3. **Maintainability**
- Changes to behavior don't require code changes
- MCP servers are isolated and testable
- Clear separation between reasoning (Playbooks) and tools (MCP)

### 4. **Verifiability**
- Compiles to PBAsm for inspection
- Step-by-step execution visible in logs
- Easier to debug than graph-based frameworks

### 5. **Flexibility**
- Easy to add new capabilities
- Subagents can be defined inline or in separate files
- MCP servers can be shared across projects

### 6. **Portability**
- Natural language is LLM-agnostic (less framework lock-in)
- MCP is a standard protocol
- Can migrate to different LLM providers easily

---

## When to Use Which?

### Use Original DeepAgents When:
- You need tight integration with LangGraph ecosystem
- You prefer Python-first development
- You want to use existing LangChain tools directly
- You need the full LangGraph Studio experience

### Use Playbooks When:
- Behavior specification and readability are priorities
- You want minimal boilerplate
- You need stakeholder-readable agent definitions
- You prefer natural language over orchestration code
- You want framework-agnostic tool definitions (MCP)

---

## Migration Steps

To migrate an existing DeepAgents project:

1. **Identify core agent behavior** - What does your agent do?
2. **Extract tool implementations** - Move to MCP servers
3. **Define agent workflows** - Write in natural language in `.pb` files
4. **Map subagents** - Convert to Playbooks multi-agent structure
5. **Test incrementally** - Verify behavior matches original
6. **Simplify** - Remove boilerplate and orchestration code

---

## Conclusion

The Playbooks implementation achieves the same functionality as DeepAgents with:
- **77% less code**
- **Better readability** for non-technical stakeholders
- **Cleaner architecture** with MCP separation
- **Framework-agnostic** tool definitions
- **Built-in debugging** and development tools

The trade-off is less direct control over the execution graph, but for most coding agent use cases, the high-level behavioral specification is sufficient and more maintainable.

