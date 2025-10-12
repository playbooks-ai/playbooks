# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.6.1] - 2025-10-11

### Added

- **LangGraph Example** - Added comprehensive tax agent implementation using LangGraph as a comparison example

### Improved

- **Error Handling** - Gracefully display missing LLM API key errors from the CLI with helpful messages
- **Dependencies** - Upgraded all dependencies to address security vulnerabilities

### Fixed

- **CreateAgent Streaming** - Fixed issue #37 where dynamically created agents using `CreateAgent()` didn't stream output properly

---

## [0.6.0] - 2025-09-27

### Added

#### Agent System & Communication
- **Dynamic Agent Creation** - New `CreateAgent()` function for instantiating agents dynamically at runtime
- **Direct Agent-to-Agent Messaging** - Improved BGN playbooks and idle loop processing for seamless inter-agent communication. Now directives such as `ask Accountant for gross salary` will work.
- **Targeted Communication** - `Say()` and `YLD` functions can now target specific agents, meetings, or users
- **Ambient Agents** - All agents now run ambiently and require explicit exit
- **Busy tracking** - Using `$_busy` variable to track if an agent is busy, so inbound messages can be handled appropriately.

#### Meeting Management
- **Meeting Playbooks** - Support for automatic and explicit meeting invitations
- **Meeting Orchestration** - Wait for required attendees with configurable timeouts
- **Meeting Broadcasting** - Messages broadcast to all attendees via meeting owner
- **Meeting Tracking** - Track and manage ongoing meetings across agents

#### Streaming & Real-time Features  
- **Progressive Streaming** - Optimistic parsing for `Say()` function enables real-time output
- **Multi-interface Streaming** - Command line, web server, and Streamlit app all support streaming
- **Async/Sync Playbooks** - Both async and sync Python playbooks are now supported

#### Configuration System
- **playbooks.toml** - Centralized configuration file for settings, including model settings with fallback support
- **Per-Agent Model Configuration** - Individual agents can have custom model configurations

#### Web Playground & Server
- **Web Server Command** - New `webserver` CLI command for running the web interface
- **Playground Command** - New `playground` CLI command with auto-opening browser support
- **Standalone Playground** - HTML-based interactive playground application for testing

#### Built-in Playbooks
- **SetVar Playbook** - New builtin function for variable assignment with return values
- **LoadFile Playbook** - Builtin function for file loading operations
- **CreateAgent Playbook** - Dynamic agent instantiation during runtime

#### Development Experience
- **Import Processor** - New `!import` directive for modular playbook composition
- **Unified Debug Logger** - Centralized debug logging with environment-driven configuration

### Improved

#### LLM & Context Management
- **Context Compaction** - Automatic LLM context compression for longer conversations
- **LLM Playbook Types** - Support for three types: `playbook` (steps), `react`, and `raw`
- **Typed Message System** - `LLMMessage` type for better prompt management
- **Playbook Description Placeholders** - Dynamic placeholder resolution in descriptions
- **Deterministic Cache Keys** - Consistent LLM caching across different environments
- **Return values** - Use expression engine for parsing return values to support expression like `Return[$amount * 2]`

#### Debugging Experience
- **VSCode Integration** - Enhanced step debugging with accurate source line mapping
- **Specific Agent Debugging** - Debug individual agents in VSCode represented as threads
- **Graceful Shutdown** - Automatic termination of debug process when client disconnects
- **Breakpoint Normalization** - Path normalization for reliable breakpoint checks

#### Markdown Playbooks
- **Semantic Message Handling** - Markdown playbooks can handle inbound messages semantically
- **Idle Loop Processing** - Enhanced idle loop and message handling capabilities
- **Source Preservation** - Original markdown preserved for accurate line numbers during debugging
- **H2 Block Separation** - Visual separators after each H2 block in .pbasm for better readability

#### Architecture & Performance
- **Event System Unification** - Merged program and debug event systems into single, cohesive architecture
- **Async EventBus** - Combined sync/async event handling with proper lifecycle management
- **Parallel Compilation** - Per-agent compilation caching with `.pbasm_cache` files
- **Variable Resolution Engine** - Enhanced expression engine for improved variable handling
- **Trigger Step Tracking** - Triggers now produce `Step[]` for better execution tracking

#### Testing & Quality
- **Test Coverage** - Overall coverage improved from 77% to 79%
- **Event System Tests** - Added 85 comprehensive tests for event types and EventBus
- **Edge Case Handling** - 97 new tests covering error conditions and edge cases

### Changed

#### System Requirements
- **Python Version** - Upgraded minimum requirement to Python 3.12

#### Event Architecture
- **Unified Events** - All events now use `agent_id` instead of `thread_id`
- **Immutable Events** - Events are now frozen dataclasses for safety
- **Single Event Module** - Debug events moved from `debug.events` to main events module

#### Compilation
- **Composite Steps** - PBAsm uses composite steps to maintain control during multi-turn conversations
- **Cache File Usage** - Compiler now uses `.pbasm_cache` files when available

### Fixed

- **Duplicate List Items** - Fixed duplicated nested list items in markdown processing
- **VSCode Thread Management** - Fixed "stopped" events for paused agents when continuing specific agent
- **Test Naming** - Renamed classes starting with "Test" to avoid pytest confusion
- **Path Issues** - Fixed path normalization for reliable breakpoint handling
- **LiteLLM Authentication** - Graceful handling of authentication errors
- **Langfuse Integration** - Tests can now run without Langfuse dependency
- **Immutable Events** - All events are now frozen dataclasses preventing accidental modification
- **Thread-Safe Configuration** - Ensured thread-safe configuration in centralized constants

### Dependencies

- **New Dependencies**:
  - `bidict` - Bidirectional dictionary support

---

## [0.5.0] - Skipped

Skipped to align with VSCode extension release 0.6.0

---

## [0.4.0] - 2025-06-15

### Added

#### MCP Integration & Agent Architecture
- **MCP Servers as Agents** - Support for Model Context Protocol servers as remote agents
- **Transport Layer** - New transport layer for MCP communication
- **Agent Class Hierarchy** - Structured hierarchy with AIAgent, LocalAIAgent, and RemoteAIAgent
- **Cross-Agent Playbook Calls** - Call playbooks across agents within the same program

#### Developer Experience
- **VSCode Debugging Support** - Full debugging integration with VSCode
- **CLI Tool** - New `playbooks` command-line interface
- **File Extension Support** - Recognition of `.pb` and `.pbc` extensions as Playbooks

#### Playbook Features
- **Metadata System** - Metadata support for agents and playbooks with public/private visibility
- **Execution Summary** - Generate playbook execution summary in `$__` variable
- **Stack-Based Context** - New context management system

### Improved

#### LLM & Caching
- **LLM Caching** - Optimized to keep only up to 4 cached messages (Anthropic max)
- **Cache Control Preservation** - Maintain cache control on system messages
- **Message Consolidation** - Consolidate messages while preserving cache control
- **Default Model** - Switched to Claude Sonnet 4.0 as default

#### Playbook Architecture
- **Class Hierarchy** - New structured hierarchy: LocalPlaybook (Markdown/Python) and RemotePlaybook
- **Async/Sync Support** - Allow both sync and async Python playbooks
- **Control Flow** - Compiler adds control flow for form filling and multi-turn conversations
- **Variable Handling** - Exclude null and private variables (starting with `$_`) from prompts

### Changed

- **Assembly Language** - Changed CLS to Assembly Language terminology
- **Compiler Prompt** - Restructured and refined compiler prompt
- **Execution Prompt** - Refined with unexpected situation examples

### Fixed

- **Variable Substitution** - Fixed issue where `Say("This $blah")` showed as "This __substituted__blah"
- **Type Setting** - Fixed setting variables with type annotations (e.g., `Var["$var1:str", "abcd"]`)
- **Python Triggers** - Ensured Python playbook triggers are processed and listed in exports.json

---

## [0.3.0] - 2025-05-04

### Added

#### Core Architecture
- **Full Reimplementation** - Complete framework rewrite for improved performance and reliability
- **JSON Output Format** - Switched from YAML to JSON for more reliable LLM output
- **Python AST Parser** - Added for function call parsing
- **Code Playbooks Triggers** - Support for triggers in code playbooks
- **RAG Retrieval Playbook** - New playbook type for retrieval-augmented generation

#### Documentation & Observability
- **GitHub Pages Documentation** - Documentation site hosted on GitHub Pages
- **Langfuse Tracing** - Integration for execution tracing and monitoring
- **Markdown Output** - Support for markdown-formatted output

#### Language Features
- **Single Playbook Mode** - Streamlined execution mode for single playbooks
- **Natural Language Programming** - Enhanced support for natural language instructions
- **Improved Conditionals** - Added ELS instruction for else branches
- **Loop Improvements** - Better loop execution with JMP instructions

### Improved

#### Execution Engine
- **Playbook Steps DAG** - Directed Acyclic Graph for step management
- **Interpreter Execution** - Major improvements to interpreter execution logic
- **Conditional Blocks** - Better handling of conditional execution blocks
- **Search Query Generation** - Improved generation of search queries
- **External Tool Calling** - Fixed and improved external tool integration

#### Developer Experience
- **Prompt Caching** - Static parts as system messages, dynamic as user messages
- **Transpiled Content** - Save to temp file for easy review
- **Test Coverage** - Expanded test suite with LLM caching
- **Base Prompt** - New base prompt for generating playbooks programs

### Changed

- **Default Model** - Changed to gpt-4o-mini for better loop handling
- **Max Iterations** - Added limits for execution iterations
- **News Mode** - Added for searching recent events
- **YAML Enforcement** - Force YAML-only mode for specific use cases

### Fixed

- **Loop Execution** - Fixed issues with loops truncating output
- **Multi-line Format** - Corrected YAML multi-line formatting
- **Step Continuation** - Fixed step numbering in loop continuations
- **Return Handling** - Fixed call stack management when returning from playbooks

---

## [0.2.0] - 2025-02-24

### Added

#### Core Features
- **Agent System** - Complete Agent and AgentChat application implementation
- **Single Playbook Mode** - New streamlined execution mode
- **Loop Support** - Full support for loops with JMP instructions
- **Multiple Tool Calls** - Support for multiple concurrent tool invocations
- **Session Management** - Session and conversation context for CLI

#### LLM & Integration
- **LiteLLM Integration** - Switched to LiteLLM for model management
- **LLM Caching** - Implemented caching with automatic cache key generation
- **Prompt Caching** - Optimized with static/dynamic message separation
- **Memory System** - Simple memory for agent threads

#### Developer Tools
- **Pre-commit Hooks** - Check .litellm_cache changes before commit
- **Test Infrastructure** - Comprehensive test suite with mocked LLM responses
- **Coverage Reporting** - Added test coverage tracking
- **Code Organization** - Major code reorganization for better structure

### Improved

- **Streaming** - Separated streaming vs non-streaming function handling
- **Error Handling** - Better handling of premature LLM yields with "continue"
- **Newline Preservation** - Maintain newlines in agent responses
- **Response Length** - Allow longer interpreter sessions for loops and procedures
- **Natural Language** - Use simpler, more natural language in prompts

### Changed

- **Default Model** - Switched to gpt-4o-mini as default
- **Python Version** - Downgraded to Python 3.10 for compatibility
- **Website Structure** - Reorganized website code under single directory
- **Test Approach** - No longer mock LLM responses due to LiteLLM cache

### Fixed

- **Loop Execution** - Fixed issues with loop continuation
- **Linter Errors** - Resolved all linting issues
- **Test Failures** - Fixed various test suite failures
- **Coverage Workflow** - Fixed GitHub Actions coverage workflow

---

## [0.1.0] - 2024-11-24

### Added

#### Foundation
- **Initial Release** - First public version of the Playbooks framework
- **Runtime Implementation** - Basic playbooks.ai runtime and hello world example
- **API Server** - REST API for playbook execution

#### Web Interface
- **Next.js Website** - Full website with landing page and playground
- **Chat Interface** - Basic chat with Claude Sonnet 3.5
- **Playbook Editor** - UI for editing playbooks
- **Playground Component** - Interactive playground for testing

#### Core Features
- **Chain of Thought** - Implementation for playbook execution
- **WebSockets Support** - Real-time communication capabilities
- **Markdown Rendering** - Support for markdown in chat interface
- **JavaScript Modules** - JS module system for browser execution

### Technical Details

- **Streaming Support** - Basic streaming implementation
