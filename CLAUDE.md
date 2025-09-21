# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Playbooks** is an innovative Python framework for building and executing AI agents using "playbooks" – structured workflows defined in natural language (via Markdown-based .pb files) or Python code. This framework represents a significant step toward Software 3.0, where natural language becomes a first-class programming language.

## Core Architecture

### Framework Components

#### 1. Language & Execution
- **Natural Language Programming**: Write workflows in plain English that compile to executable code
- **Hybrid Execution Stack**: Seamless interoperability between Markdown (natural language) and Python execution
- **Compiler-Driven Reliability**: `.pb` files compile to `.pbasm` (assembly) format with semantic static analysis

#### 2. Agent System
- **Multi-Agent Architecture**: Built-in support for distributed agents with communication protocols
- **Agent Types**: Local AI agents, remote AI agents, human agents, MCP agents, system agents
- **Agent Registry**: Dynamic agent discovery and integration capabilities

#### 3. Execution Engine
- **Program Class**: Core execution orchestrator managing playbook lifecycle
- **Event-Driven Architecture**: Reactive programming with triggers and event bus
- **Call Stack Management**: Unified call stack for both natural language and Python execution

### Key Architectural Insights

#### Compilation Pipeline
The compilation flow from `.pb` → `.pbasm` involves:
1. **Loader** (`loader.py`) reads and validates playbook files
2. **Compiler** (`compiler.py`) uses LLM to preprocess content, adding line type codes (QUE, CND, etc.)
3. **AST Generation** (`markdown_to_ast.py`) converts compiled content to executable structure
4. **Program** (`program.py`) orchestrates execution using the compiled AST

#### Agent Threading Model
- Migrated from threading to pure async/await architecture (`AsyncAgentRuntime` in `program.py`)
- Each agent runs as an independent asyncio task
- Message passing between agents is handled through the event bus
- Agent lifecycle managed through `start_agent()` and `stop_agent()` methods

#### Message Flow Architecture
1. **Messages** created with specific types (MessageType enum)
2. **Event Bus** (`event_bus.py`) handles message routing between agents
3. **Agents** subscribe to specific message patterns
4. **Execution State** (`execution_state.py`) maintains context across message handling

#### Playbook Execution Modes
- **Local Playbooks**: Direct execution within the same process
- **Remote Playbooks**: Network-based execution via MCP transport
- **Python Playbooks**: Direct Python function execution with decorator support
- **LLM Playbooks**: Dynamic playbook generation and execution

#### MCP Integration
- **Transport Layer** (`transport/mcp_transport.py`): Handles WebSocket/SSE connections
- **MCP Agents** (`mcp_agent.py`): Bridge between MCP servers and playbook system
- **Protocol** (`transport/protocol.py`): Defines message format and handshake

## Key Features

### 1. Compilation System
- **Semantic Static Analysis**: Infers intent, adds annotations (QUE, CND), variables/types
- **Intermediate Representation**: `.pb` → `.pbasm` compilation for reliable execution
- **Runtime Optimization**: Reduces LLM hallucinations through structured guidance

### 2. Agent Communication
- **MCP (Model Context Protocol)**: Standard for agent-to-agent communication
- **Transport Layer**: WebSocket, SSE, and other transport protocols
- **Message Routing**: Intelligent message routing between agents

### 3. Development Tools
- **CLI Interface**: Command-line tools for running and compiling playbooks
- **VSCode Extension**: Debugging and development support
- **Rich Console Output**: Enhanced terminal experience with rich formatting

## Project Structure

```
playbooks/
├── src/playbooks/
│   ├── agents/           # Agent implementations and registry
│   ├── applications/     # Application interfaces (CLI, web, Streamlit)
│   ├── common/          # Shared utilities and logging
│   ├── debug/           # Debugging infrastructure
│   ├── meetings/        # Meeting management system
│   ├── playbook/        # Playbook implementations (local, remote, etc.)
│   ├── prompts/         # LLM prompts and templates
│   ├── transport/       # Communication protocols
│   └── utils/           # Utility functions and helpers
├── tests/               # Test suite
│   ├── data/           # Test playbooks and examples
│   └── unit/           # Unit tests
└── docs/               # Documentation
```

## Core Classes & Modules

### Essential Components

#### Main Entry Points
- `main.py`: Primary Playbooks class orchestrating the entire framework
- `cli.py`: Command-line interface for running and compiling playbooks
- `compiler.py`: Compiles `.pb` files to `.pbasm` intermediate representation

#### Execution Engine
- `program.py`: Core execution orchestrator managing playbook lifecycle
- `execution_state.py`: Manages execution state and context
- `call_stack.py`: Unified call stack for hybrid execution
- `event_bus.py`: Event-driven architecture for reactive programming

#### Agent System
- `agents/base_agent.py`: Abstract base class for all agent types
- `agents/ai_agent.py`: AI-powered agent implementation
- `agents/registry.py`: Dynamic agent discovery and registration
- `agents/messaging_mixin.py`: Message handling capabilities

#### Playbook Management
- `playbook/base.py`: Base playbook implementation
- `playbook/markdown_playbook.py`: Markdown-based playbook execution
- `playbook/python_playbook.py`: Python-based playbook execution
- `markdown_playbook_execution.py`: Markdown execution engine

## Common Development Commands

### Setup & Installation
```bash
# Install dependencies using Poetry
poetry install

# Set up environment
cp .env.example .env
# Edit .env to specify ANTHROPIC_API_KEY
```

### Running Tests
```bash
# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest tests/unit/playbooks/test_compiler.py

# Run tests with coverage
poetry run pytest --cov=src/playbooks --cov-report=html

# Run tests matching a pattern
poetry run pytest -k "test_compilation"

# Run tests in verbose mode
poetry run pytest -v
```

### Code Quality
```bash
# Format code with black
poetry run black .

# Run linting checks
poetry run ruff check .

# Fix linting issues automatically
poetry run ruff check . --fix
```

### Building & Distribution
```bash
# Build the package
poetry build

# Install in development mode
poetry install
```

### Running Playbooks
```bash
# CLI execution
playbooks run example.pb

# Compile a playbook to .pbasm
playbooks compile example.pb

# Run with debugging enabled
playbooks run --debug example.pb

# Programmatic execution (async context required)
from playbooks import Playbooks
pb = Playbooks(["example.pb"])
await pb.initialize()
await pb.program.run_till_exit()
```

## Technical Requirements

### Dependencies
- **Python**: 3.12+
- **Core Libraries**: 
  - `rich` for enhanced console output
  - `litellm` for LLM integration
  - `fastmcp` for MCP protocol support
  - `langfuse` for observability
  - `redis` for caching and state management

### Development Tools
- **Testing**: pytest with asyncio support
- **Linting**: ruff for code quality
- **Formatting**: black for code formatting
- **Package Management**: Poetry for dependency management
- **Environment Variables**: .env file for API keys and configuration

## Current Development Status

### Recent Changes (from git status)
- Agent threading improvements in `ai_agent.py`
- LLM response handling enhancements
- Markdown playbook execution refinements
- Test suite updates and improvements

### Active Development Areas
- Multi-agent coordination and threading
- Enhanced LLM response processing
- Improved test coverage and reliability
- MCP protocol integration

## Usage Patterns

### 1. Conversational Agents
```python
# Multi-turn dialogue management
# Trigger-based reactive responses
# Hybrid Python/English logic
```

### 2. Task Automation
```python
# Workflow orchestration
# Data processing pipelines
# Error handling and recovery
```

### 3. Multi-Agent Systems
```python
# Distributed agent coordination
# Specialized agent roles
# Communication protocols
```

## Best Practices

### 1. Playbook Design
- Use clear, descriptive natural language
- Define explicit triggers and conditions
- Leverage hybrid execution for complex logic
- Implement proper error handling

### 2. Agent Development
- Follow the base agent interface
- Implement proper message handling
- Use the registry for dynamic discovery
- Ensure thread safety for concurrent operations

### 3. Testing
- Write comprehensive unit tests
- Use the test data examples as templates
- Test both synchronous and asynchronous execution
- Validate compilation and execution separately

## Advanced Features

### 1. Dynamic Program Generation
- Runtime playbook creation and compilation
- LLM-generated workflows based on reasoning
- Adaptive program composition

### 2. Verifiability Constraints
- Pre-condition and post-condition validation
- Self-validating workflows
- Intelligent program deviation handling

### 3. Distributed Execution
- Multi-agent program execution
- Remote playbook invocation
- Cross-agent state management

## Future Roadmap

### Near-term Goals
- Enhanced debugging capabilities
- Improved VSCode extension features
- Better error reporting and recovery
- Performance optimizations

### Long-term Vision
- AGI-friendly programming paradigms
- Advanced program synthesis
- Intelligent program search and optimization
- Enterprise-scale deployment patterns

## Contributing

### Development Setup
```bash
# Clone repository
git clone <repository-url>
cd playbooks

# Install dependencies
poetry install

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Run tests to verify setup
poetry run pytest

# Format and lint code before committing
poetry run black .
poetry run ruff check . --fix
```

### Code Standards
- Follow existing code patterns and conventions
- Write comprehensive tests for new features
- Document public APIs and complex logic
- Ensure backwards compatibility
- All async functions should properly handle cancellation
- Use type hints for public APIs

## Resources

- **Documentation**: https://playbooks-ai.github.io/playbooks-docs/
- **Homepage**: https://runplaybooks.ai/
- **License**: MIT
- **Python Version**: 3.12+
- **Package Manager**: Poetry

## Debugging & Development Tips

### Debugging Playbooks
```bash
# Enable debug mode for verbose output
playbooks run --debug example.pb

# Use the VSCode extension for step-by-step debugging
# Set breakpoints in .pb files after installing the extension
```

### Common Issues & Solutions
1. **Async Context Errors**: Ensure all playbook execution happens within async context
2. **Agent Communication**: Check event bus subscriptions if agents aren't receiving messages
3. **Compilation Errors**: Validate playbook structure - requires agent name header and proper sections
4. **MCP Connection Issues**: Verify MCP server is running and transport URLs are correct

### Performance Considerations
- Use caching for compiled playbooks (enabled by default)
- Agent tasks run concurrently - design message handlers to be thread-safe
- LLM calls can be expensive - use appropriate models for the task

## Keywords for Claude Code

When working with this codebase, focus on:
- **Natural language programming** and compilation
- **Agent-based architecture** and communication
- **Hybrid execution** of Markdown and Python
- **Event-driven programming** with triggers
- **Multi-agent systems** and coordination
- **LLM integration** and response handling
- **Async/await patterns** throughout the codebase
- **Test-driven development** with pytest
- **MCP protocol** for inter-agent communication
- **Playbook compilation** and AST generation