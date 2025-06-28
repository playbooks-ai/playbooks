⏺ 6-Phase Implementation Plan for Streaming Support

  Phase 1: Streaming Infrastructure Foundation

  Goal: Establish basic streaming infrastructure without changing existing behavior

  Deliverables

  1. New streaming module structure:
  src/playbooks/streaming/
  ├── __init__.py
  ├── base.py              # StreamingCall base class
  ├── streaming_call.py    # StreamingSendMessage implementation
  └── events.py            # Streaming events
  2. Core classes:
    - StreamingCall (abstract base)
    - StreamingSendMessage (concrete implementation)
    - MessageStreamStartEvent, MessageStreamUpdateEvent, MessageStreamCompleteEvent
  3. Configuration support:
    - Add streaming_enabled: bool = False to LLMConfig
    - Environment variable PLAYBOOKS_STREAMING_ENABLED

  Testing Strategy

  - Unit tests for StreamingSendMessage class
  - Event emission tests
  - Configuration loading tests
  - All existing tests must pass unchanged

  Success Criteria

  - New streaming classes work in isolation
  - Configuration system integrated
  - Zero impact on existing functionality
  - Full test suite passes

  ---
  Phase 2: Pattern Detection Engine

  Goal: Build the pattern detection system for recognizing streaming calls

  Deliverables

  1. Pattern matching system:
  src/playbooks/streaming/
  ├── pattern_matcher.py   # CallPatternMatcher
  └── call_detector.py     # StreamingCallDetector (basic version)
  2. Core functionality:
    - Detect Say(" and SendMessage("human", " patterns
    - Handle partial tokens across boundaries
    - Buffer management for incomplete patterns
    - Quote escaping support
  3. Test suite:
    - Pattern recognition with various inputs
    - Partial token handling
    - Edge cases (escaped quotes, malformed calls)

  Testing Strategy

  - Isolated unit tests with mock token streams
  - Property-based testing for edge cases
  - Performance tests for pattern matching
  - Integration tests with real LLM response samples

  Success Criteria

  - Reliably detects streaming call patterns
  - Handles all edge cases gracefully
  - Performance acceptable for real-time streaming
  - No false positives/negatives in test cases

  ---
  Phase 3: LLM Response Streaming Integration

  Goal: Integrate streaming detection with LLM response processing

  Deliverables

  1. Modified LLM execution:
    - Update MarkdownPlaybookExecution.make_llm_call() to support streaming mode
    - New make_llm_call_streaming() method
    - Integration with StreamingCallDetector
  2. Streaming response processing:
    - Stream tokens through pattern detector
    - Initialize streaming calls when detected
    - Maintain existing LLMResponse compatibility
  3. Configuration integration:
    - Check streaming_enabled flag
    - Fallback to non-streaming on errors

  Testing Strategy

  - Mock LLM streaming responses
  - Test with real playbook files containing Say() calls
  - Verify both streaming and non-streaming modes work
  - Performance comparison between modes

  Success Criteria

  - Streaming calls are detected and started during LLM response
  - Non-streaming mode works exactly as before
  - Error handling gracefully falls back to non-streaming
  - Real playbook examples work correctly

  ---
  Phase 4: Agent Communication Streaming

  Goal: Implement streaming message delivery to target agents

  Deliverables

  1. Enhanced agent communication:
    - Modify BaseAgent.SendMessage() to support streaming
    - Update Program.route_message() for streaming delivery
    - Streaming message queues in agent inboxes
  2. Message queue system:
    - Streaming message updates delivered in real-time
    - Proper completion handling
    - Maintain message ordering
  3. Backward compatibility:
    - Existing SendMessage calls work unchanged
    - Streaming and non-streaming messages can coexist

  Testing Strategy

  - Multi-agent communication tests
  - Message ordering verification
  - Mixed streaming/non-streaming scenarios
  - Performance tests with high message volume

  Success Criteria

  - Streaming messages reach target agents in real-time
  - Message ordering preserved
  - All existing communication tests pass
  - Performance meets real-time requirements

  ---
  Phase 5: CLI Application Streaming

  Goal: Add streaming display to the agent_chat CLI application

  Deliverables

  1. Streaming UI components:
    - StreamingSessionLogWrapper class
    - Progressive Rich panel updates
    - Real-time message display with typing indicators
  2. Enhanced user experience:
    - Messages appear as they're generated
    - Visual indicators for streaming state
    - Graceful handling of connection issues
  3. Configuration options:
    - Command-line flag to enable/disable streaming
    - Fallback to non-streaming mode

  Testing Strategy

  - Manual testing with various playbook files
  - Automated UI tests using Rich's testing framework
  - Performance tests with long messages
  - Error scenario testing (network issues, LLM errors)

  Success Criteria

  - Users see messages appearing in real-time
  - UI remains responsive during streaming
  - Error states handled gracefully
  - Existing CLI functionality unchanged

  ---
  Phase 6: Web Application Streaming

  Goal: Add streaming support to the web agent chat application

  Deliverables

  1. Streaming API endpoints:
    - New /runs/{session_id}/stream endpoint
    - Server-sent events for real-time updates
    - JSON streaming message format
  2. Enhanced web interface:
    - Real-time message updates in browser
    - WebSocket or SSE connection management
    - Progressive message rendering
  3. API compatibility:
    - Existing HTTP endpoints work unchanged
    - Backward compatibility for existing clients
    - Optional streaming for new clients

  Testing Strategy

  - API endpoint testing with various clients
  - WebSocket/SSE connection reliability tests
  - Browser compatibility testing
  - Load testing with multiple concurrent streams

  Success Criteria

  - Web clients receive real-time message updates
  - API remains backward compatible
  - Performance suitable for production use
  - Multiple concurrent sessions supported

  ---
  Cross-Phase Considerations

  Dependencies

  - Phase 1 → Phase 2: Base classes needed for pattern detection
  - Phase 2 → Phase 3: Pattern detection needed for LLM integration
  - Phase 3 → Phase 4: LLM streaming needed for agent communication
  - Phase 4 → Phase 5: Agent communication needed for CLI streaming
  - Phase 5 ↔ Phase 6: Independent (can be developed in parallel)

  Rollback Strategy

  Each phase includes:
  - Feature flags to disable new functionality
  - Automatic fallback to previous behavior on errors
  - Configuration to revert to non-streaming mode
  - Monitoring and alerting for issues

  Testing Continuity

  - All existing tests must pass after each phase
  - New tests added incrementally
  - Performance regression testing
  - Integration testing across phases

  Documentation Updates

  - Update CLAUDE.md after Phase 3 (core functionality)
  - API documentation after Phase 6
  - User guides for CLI and web applications

⏺ Update Todos
  ⎿  ☒ Create phase-by-phase implementation plan
     ☒ Define testing strategy for each phase
     ☒ Identify dependencies between phases
     ☒ Document deliverables per phase
     ☒ Plan rollback strategies

⏺ Implementation Timeline Summary

  This 6-phase plan builds streaming support incrementally while maintaining system stability:

  Phase 1-2: Foundation (1-2 weeks)

  - Streaming infrastructure and pattern detection
  - No behavior changes, just new capabilities
  - Extensive unit testing

  Phase 3-4: Core Integration (2-3 weeks)

  - LLM streaming and agent communication
  - First functional streaming behavior
  - Integration testing with real playbooks

  Phase 5-6: User Interfaces (1-2 weeks each)

  - CLI and web streaming experiences
  - Can be developed in parallel
  - User acceptance testing

  Key Benefits of This Approach:

  ✅ Incremental Risk: Each phase adds limited complexity
  ✅ Continuous Testing: All existing functionality preserved
  ✅ Early Feedback: Streaming behavior visible from Phase 3
  ✅ Parallel Development: Phases 5-6 can be concurrent
  ✅ Rollback Safety: Feature flags and fallbacks at each level

  Testing Confidence:

  - Existing test suite passes throughout
  - New functionality tested in isolation first
  - Integration testing builds progressively
  - Real-world scenarios validated early

  This plan ensures streaming support is delivered reliably while maintaining the robustness that makes Playbooks AI suitable
   for production use.