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