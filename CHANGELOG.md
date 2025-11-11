# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [v0.7.0] - 2025-11-10

### Added

#### Multi-Human Support (Fixes #62)
- **Declarative Human Agent Syntax** - Applications often need to coordinate multiple human users (e.g., customer service scenarios with customers and agents, or meetings with multiple stakeholders). Added `# Name:Human` agent type annotations in playbook headers to declare human agents explicitly, making multi-user coordination a first-class concept in the framework.
- **Per-Human Delivery Preferences** - Different humans have different interaction needs (some want real-time streaming, others prefer buffered messages). Implemented configurable delivery preferences per human agent, allowing fine-grained control over how messages are delivered to each participant.
- **Targeted Streaming** - In multi-human scenarios, not everyone needs to see every message in real-time. Added observer filtering by recipient with explicit recipient_id in stream events, enabling selective message streaming to specific participants.
- **Multi-Human Meetings** - Real-world coordination involves groups, not just pairs. Added support for meetings with multiple human participants and configurable notification preferences (all/targeted/none) to handle complex group interactions.
- **Backward Compatibility** - Existing single-user applications shouldn't break. Automatically creates a default User:Human agent when no humans are explicitly defined, ensuring seamless migration.

#### Real-Time Execution
- **Incremental Code Execution** - LLM-produced code execution had to wait until the entire code block was generated, causing delays before any processing can begin. Note that due to Say() streaming, user would see the message streaming already. Implemented incremental code parsing that executes complete Python statements as they're produced by the LLM chunk by chunk, dramatically improving perceived program responsiveness. Fixes #63
- **StreamingPythonExecutor** - Executing partial code safely requires careful boundary detection. Created a new executor that identifies complete statements incrementally as code chunks arrive, executing them immediately while buffering incomplete statements.
- **Real-Time Variable Tracking** - Users couldn't see intermediate results as the LLM reasoned through problems. Added namespace inspection to track variable changes in real-time during LLM generation, making the agent's thought process transparent.
- **Graceful Error Recovery** - Streaming execution errors would abort the entire process, losing partial work. Implemented error capture that sends streaming errors back to the LLM for intelligent retry without aborting execution, enabling self-correction via LLM.
- **Backward Walking Algorithm** - Determining valid execution boundaries in partial code is non-trivial. Implemented an algorithm that walks backwards from the last non-whitespace line to find valid executable prefixes, ensuring only complete statements are executed.

#### Observability & Debugging
- **Langfuse Additional Logging** - Debugging agent behavior required reading through logs or guessing at execution flow. Integrated comprehensive Langfuse logging for all Python capture functions (Step, Var, Artifact, Trigger, Return, Yld), providing visual execution traces. Fixes #64
- **Enhanced Readability** - Generic span names made traces hard to follow. Step content is now included in Step() span names (e.g., "Step: Calculate total price"), dramatically improving trace readability.
- **Snoop Mode** - Multi-agent communication was invisible during development, making debugging difficult. Added `--snoop` CLI flag and agent_chat debugging to observe all agent message exchanges in real-time.

#### Type Safety & Architecture
- **Type-Safe Identifiers** - Agent and Meeting IDs were stringly-typed, leading to parsing bugs and unclear code. Created identifiers.py with structured AgentID and MeetingID types, providing compile-time safety and clear semantics.
- **Elimination of String IDs** - 250+ lines of brittle string parsing code was error-prone and hard to maintain. Removed all stringly-typed ID parsing by migrating to structured identifier types.
- **Structured ID Operations** - Common operations like equality and hashing were inconsistent with string IDs. Implemented type-safe equality, hashing, and string conversion on identifier types for reliable behavior.
- **DeliveryPreferences Configuration** - Delivery behavior was scattered across the codebase. Created delivery_preferences.py to centralize and make explicit all delivery control configuration.
- **HumanState System** - Human agents don't need the complex state that AI agents maintain, wasting memory. Implemented minimal state tracking for human agents, reducing memory footprint by 90% vs AI agents.
- **StreamResult Flow Control** - Streaming control flow was implicit and confusing. Added explicit streaming control flow with new stream_result.py module for clear, maintainable streaming logic.

### Improved

#### Event-Driven Architecture
- **Asyncio Event Coordination** - Polling loops consumed CPU and added latency to message delivery. Replaced all polling loops with asyncio.Event throughout the system, eliminating busy-waiting and reducing latency.
- **Atomic Channel Creation** - Race conditions during concurrent channel creation caused message loss. Implemented atomic channel initialization that's race condition-free, ensuring reliable message delivery.
- **Error Isolation** - Errors in one callback could cascade and crash the entire system. Properly isolated callback errors to prevent cascade failures while maintaining system stability.
- **Single Message Queue** - Dual buffer system added complexity and potential for message reordering. Eliminated dual buffers in favor of a single message queue for cleaner, more predictable message routing.
- **Observer Pattern Enhancement** - Determining which observers should receive messages required complex logic. Added Meeting.should_stream_to_human() logic for explicit, declarative targeted streaming decisions.

#### Caching & Performance
- **Stack Frame Based Caching** - Type-based caching missed optimization opportunities across execution contexts. Switched to frame-based LLM message caching where the last message in each call stack frame is marked for caching, maximizing cache prefix reuse. Fixes #66

#### Message & Context Management
- **User Instruction Compaction** - Long conversations filled context windows with repeated instructions. Implemented instruction compression to improve context window utilization without losing critical information.
- **Compact Message Format** - Verbose message formatting wasted tokens. Use compact message format in LLM context for better token efficiency and reduced API costs.
- **Message Format Consistency** - Streaming and non-streaming modes produced different message formats, complicating downstream code. Fixed format differences to ensure consistent message structure regardless of delivery mode.

#### Code Quality & Organization
- **Code Reorganization** - Organic growth led to unclear module boundaries and circular dependencies. Major restructuring with git mv to establish clear separation of concerns and better project layout.
- **Absolute Path Imports** - Mix of relative and absolute imports caused confusion and import errors. Standardized on absolute imports throughout codebase for clarity and reliability.
- **Test Organization** - Tests were scattered and hard to navigate. Comprehensive test suite reorganization with consistent structure and fixed path references.
- **Unit Test Isolation** - Tests making LLM calls were slow, expensive, and non-deterministic. Disallow LLM calls from unit tests to ensure fast, deterministic testing.
- **SpecUtils Module Removal** - Deprecated SpecUtils module lingered, causing confusion. Cleaned up deprecated code to reduce maintenance burden.

#### Agent System
- **Dynamic HumanAgent Factory** - Creating human agent instances required repetitive boilerplate. Implemented subclass factory for creating human agent instances dynamically based on configuration.
- **Clean Message Routing** - String-based routing was error-prone and hard to debug. Simplified routing with structured identifiers for clear, type-safe message delivery.
- **Agent Instance Targeting** - Could only target agent classes, not specific instances. Added ability to call playbooks on specific agent instances for fine-grained control, e.g. `AccountantExpert["agent 1020"].TaxRateQuery()`. Fixes #67
#### Execution & Error Handling
- **Python Execution Errors** - Execution errors terminated processing without giving the LLM a chance to fix them. Send execution errors back to LLM for intelligent retry, enabling self-healing execution.
- **UnboundLocalError Handling** - Reading variables before assignment caused cryptic errors. Fixed to properly detect and report when variables are read before being assigned.
- **End-of-Message Handling** - EOM markers weren't consistently handled across communication types. Implemented proper EOM handling in all communication channels.
- **ReAct Mode Auto-Selection** - Users had to manually specify execution_mode even for simple cases. Automatically set execution_mode:react when no Steps specified and no execution_mode given.

#### Developer Experience
- **VSCode Launch Configuration** - Updated launch.json to enable snoop by default for better out-of-box debugging experience.
- **Improved Error Context** - Stack traces were missing for some error conditions. Enhanced error logging with complete stack traces for all error paths.
- **Streaming Infrastructure** - Stream events lacked context about recipients and meetings. Stream events now include recipient_id and meeting_id for proper filtering and routing.

### Changed

- **Default Model** - Switched to claude-haiku-4.5 for faster execution while maintaining quality for most use cases.
- **Artifact Auto-Creation** - Long variable values cluttered the prompt unnecessarily. Auto-create artifacts from Var() for values exceeding length threshold, keeping prompts clean.
- **Execution Summary Format** - Execution summaries as text were hard to browse and analyze. Playbooks execution summary now provided as structured artifact for better navigation.
- **Channel Communication** - Separate code paths for 1-on-1 vs group communication added complexity. Universal channel handles any number of participants (1, 2, or N) with single, consistent API. Fixes #65
- **Unified Communication Interface** - Three separate classes for direct messages, conversations, and meetings caused code duplication. Single Channel class handles all communication types with unified interface.
- **Message Delivery** - Hard-coded delivery logic made it difficult to add new delivery methods. Polymorphic delivery via Participant interface enables flexible, extensible delivery mechanisms.
- **Agent Arguments** - Arguments weren't available during streaming execution. Extract playbook args before LLM call to make them available during streaming for more intelligent execution.
- **Format Improvements** - Inconsistent formatting made code harder to read. Various formatting improvements for better readability and maintainability.

### Fixed

- **Streaming in CLI** - Streaming mode was enabled but no messages appeared in CLI. Fixed message display in CLI when streaming is enabled.
- **Message Format Consistency** - Streaming and non-streaming produced different JSON structures, breaking downstream code. Unified message formats between streaming and non-streaming modes.
- **Meeting Invitations** - Meeting invitations weren't properly delivered or acknowledged. Fixed invitation handling and acceptance flow for reliable meeting coordination.
- **Human Meeting Acceptance** - Humans couldn't accept meeting invitations due to state management bug. Fixed state management so humans can properly accept meetings.

### Removed

- **Deprecated SpecUtils** - SpecUtils module was deprecated but not removed, causing confusion. Removed deprecated module to clean up codebase.
- **Dual Buffer System** - Dual message buffers added complexity without clear benefit. Eliminated in favor of single message queue for simpler, more maintainable code.
- **Type-Based Caching** - Type-based cache strategy was less effective than frame-based. Removed type-based caching in favor of more efficient frame-based approach.

---

## [v0.6.2] - 2025-10-30

### Added

- Python code execution model - LLMs generate Python with capture functions (Step, Say, Var, Artifact, Trigger, Return, Yld) instead of backtick directives
- Python-only agents (Fixes #43)
- `python_executor.py` with PythonExecutor and capture functions
- `agent_proxy.py` for cross-agent communication
- Type-aware argument resolution system (Fixes #51)
  - `LiteralValue` and `VariableReference` typed wrappers
  - Playbook-type-specific resolution (external, Python, LLM)
- Variable assignment support: `$x = Func($y)` (Fixes #47)
- `$_` variable for automatic last-result capture (Fixes #52)
- Variable chaining: `Say(...) Var[$answer, $_] Return[$answer]` (Fixes #48)
- Multi-line string support with triple quotes (Fixes #55)
- String operations for artifacts (comparison, concatenation, indexing, slicing)
- Auto-load for unloaded artifacts when referenced (Fixes #59)
- Stable artifact names (Fixes #57)
- Automatic artifact creation for large results (>500 chars threshold)
- `maxTokens` and `max_llm_calls` configuration options
- Public vs private variables (underscore prefix for private)
- Type annotations in variable assignments
- Utility to compare Langfuse traces

### Changed

- Moved `Artifact` class to `variables.py` as `Variable` subclass (Fixes #50)
- Removed `llm_response_line.py` (~350 lines of regex eliminated)
- Updated `interpreter_run.txt` prompt to Python format
- Artifact threshold changed from 280 to 500 characters
- Improved streaming with placeholder resolution

### Fixed

- LoadArtifact functionality
- Parsing `true` keyword argument values
- Tests for updated `post_execute` return values

### Removed

- Backtick-based directive parsing
- `src/playbooks/artifacts.py` (consolidated into variables.py)
- Dead code cleanup

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
