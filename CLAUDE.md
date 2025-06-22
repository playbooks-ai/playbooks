# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Package Management**: This project uses Poetry for dependency management
- `poetry install` - Install dependencies
- `poetry add <package>` - Add new dependency
- `poetry run <command>` - Run commands in virtual environment

**Testing**: Uses pytest with asyncio support
- `poetry run pytest` - Run all tests (WARNING: Tests take a very long time to run)
- `poetry run pytest tests/unit/playbooks/test_<specific>.py` - Run specific test file
- `poetry run pytest -k <test_name>` - Run specific test by name
- `poetry run pytest --cov` - Run tests with coverage

**Code Quality**:
- `poetry run ruff check` - Run linting
- `poetry run ruff format` - Format code
- `poetry run black .` - Alternative code formatting

**Running Playbooks**:
- `python -m playbooks.applications.agent_chat <file.pb>` - Run playbook in CLI chat mode
- `python -m playbooks.applications.streamlit_agent_chat <file.pb>` - Run with Streamlit UI
- `playbooks <file.pb>` - Run using CLI entry point (after install)

## Core Architecture

### Three-Layer Architecture

**Program Layer**: `Program` class (src/playbooks/program.py:29) orchestrates everything
- Parses compiled playbook content using `markdown_to_ast`
- Creates agents using `AgentBuilder.create_agents_from_ast`
- Manages agent communication via message routing
- Handles execution lifecycle and debug server

**Agent Layer**: All agents inherit from `BaseAgent` (src/playbooks/agents/base_agent.py:40)
- `LocalAIAgent` - Executes playbooks locally with LLM calls
- `MCPAgent` - Connects to remote Model Context Protocol servers
- `HumanAgent` - Handles human interaction in chat applications
- `SystemAgent` - Handles system-level operations

**Playbook Layer**: Abstract `Playbook` base class (src/playbooks/playbook/base.py:7)
- `MarkdownPlaybook` - Natural language playbooks compiled from markdown
- `PythonPlaybook` - Python functions decorated with `@playbook`
- `RemotePlaybook` - Playbooks exposed via MCP protocol

### Key Processing Pipeline

1. **Compilation**: `Compiler` (src/playbooks/compiler.py:19) uses LLM to preprocess markdown playbooks, adding line types and metadata
2. **AST Generation**: `markdown_to_ast` converts compiled content to structured format
3. **Agent Building**: `AgentBuilder` (src/playbooks/agent_builder.py:19) dynamically creates agent classes from AST
4. **Execution**: Agents execute playbooks through event-driven triggers and step processing

### Agent Communication

Agents communicate via **message passing** using inbox queues:
- `SendMessage(target_agent_id, message)` - Send message to another agent
- `WaitForMessage(source_agent_id)` - Wait for message from specific agent
- Messages routed through `Program.route_message` (src/playbooks/program.py:18)

### Event System

`EventBus` (src/playbooks/event_bus.py:7) provides typed event publishing/subscription:
- Thread-safe with reentrant locks
- Supports subscribing to specific event types or all events ("*")
- Used for debugging, logging, and inter-component communication

### Playbook Format

Playbooks use structured markdown with specific sections:
```markdown
# Agent Name
Agent description

## Playbook Name
Playbook description

### Triggers
- At the beginning of the program
- When condition is met

### Steps
- Natural language instructions
- Call Python functions
- End program
```

### Built-in Playbooks

Every agent automatically gets these built-in playbooks (src/playbooks/agent_builder.py:518):
- `SendMessage(target_agent_id, message)` - Inter-agent communication
- `WaitForMessage(source_agent_id)` - Receive messages
- `Say(message)` - Send message to human agent
- `SaveArtifact(name, summary, content)` - Store artifacts
- `LoadArtifact(name)` - Retrieve artifacts

### MCP Integration

Remote agents connect via Model Context Protocol:
- Configure with `remote: {type: "mcp", url: "...", transport: "..."}` metadata
- Supports multiple transport types: sse, stdio, websocket, streamable-http
- Comprehensive validation in `_validate_mcp_configuration` (src/playbooks/agent_builder.py:142)

### Configuration

- LLM configuration via `LLMConfig` class supports multiple providers through litellm
- Environment variables loaded from `.env` files
- Session logging and state management built-in
- Caching support via diskcache and Redis

## File Structure Notes

- `src/playbooks/applications/` - Different UI interfaces (CLI, Streamlit, web)
- `src/playbooks/prompts/` - LLM prompt templates used by compiler
- `tests/data/` - Example playbook files (.pb format) for testing
- Compiled playbooks use `.pbasm` extension (playbook assembly)