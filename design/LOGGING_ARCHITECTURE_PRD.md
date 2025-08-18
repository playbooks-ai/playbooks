# Playbooks Logging Architecture PRD

**Product**: Playbooks AI Framework  
**Feature**: Unified Logging Architecture  
**Version**: 1.0  
**Date**: 2025-01-18  
**Status**: Design Phase  

## Executive Summary

The Playbooks framework currently suffers from inconsistent logging patterns, mixed output strategies, and lack of production-ready observability. This PRD defines a comprehensive logging architecture that separates concerns across different execution contexts while providing structured, performance-oriented logging for framework development, CLI interactions, and web-based applications.

## Problem Statement

### Current State Issues

1. **Mixed Output Strategies**: 25+ files contain print statements mixed with console.print() and logging calls
2. **No Context Separation**: Debug information, user output, and system logs are intermixed
3. **Framework Development Pain**: No structured logging for developers building on Playbooks
4. **Production Readiness**: Lack of observability, monitoring, and structured data for operations
5. **Multiple Execution Contexts**: Different logging needs for CLI (agent_chat.py), web (web_server.py), and framework internals

### Key Stakeholders

- **Framework Developers**: Need debug visibility into Playbooks internals
- **Playbook Authors**: Need clear feedback on their playbook execution
- **Application Developers**: Building apps on Playbooks (CLI, web, custom)
- **Operations Teams**: Need monitoring, alerting, and troubleshooting capabilities
- **End Users**: Need clean, actionable output without noise

## Goals & Objectives

### Primary Goals

1. **🔍 Developer Experience**: Rich debugging capabilities for framework development
2. **👥 User Experience**: Clean, actionable output for playbook authors and end users
3. **📊 Observability**: Production-ready logging with structured data and monitoring integration
4. **⚡ Performance**: Minimal overhead with configurable verbosity
5. **🔧 Maintainability**: Consistent patterns across all execution contexts

### Success Metrics

- **Developer Productivity**: 50% reduction in debugging time for framework issues
- **Code Quality**: 100% of print statements replaced with appropriate logging mechanisms
- **Performance**: <5ms logging overhead per operation
- **Coverage**: 100% of critical execution paths have structured logging
- **Adoption**: All new code follows logging guidelines from day one

## User Stories & Requirements

### Framework Developer Stories

**Story 1: Deep Framework Debugging**
```
As a framework developer working on agent communication,
I want structured debug logs with agent context and message flow,
So I can quickly identify and fix race conditions and message handling issues.
```

**Story 2: Performance Analysis**
```
As a framework developer optimizing execution performance,
I want timing data and resource usage logs,
So I can identify bottlenecks and measure optimization impact.
```

### Application Developer Stories

**Story 3: CLI Application Logging**
```
As a developer building agent_chat.py,
I want separate channels for user output vs debug information,
So users see clean interactions while I can debug issues.
```

**Story 4: Web Application Logging**
```
As a developer working on web_server.py,
I want WebSocket event logging and request tracing,
So I can monitor real-time interactions and debug connection issues.
```

### Operations Team Stories

**Story 5: Production Monitoring**
```
As an operations engineer,
I want structured JSON logs with correlation IDs,
So I can set up alerts and trace issues across distributed deployments.
```

**Story 6: Error Investigation**
```
As a support engineer,
I want rich error context with stack traces and execution state,
So I can quickly diagnose and resolve user-reported issues.
```

## Technical Architecture

### Logging Contexts & Separation of Concerns

#### 1. Framework Debug Logging
**Purpose**: Internal framework development and troubleshooting  
**Audience**: Framework developers  
**Format**: Structured JSON with rich context  
**Output**: File + optional console (when debug enabled)  

```python
# Example: Agent execution debugging
framework_logger.debug("Agent message processing started", extra={
    "agent_id": "user_assistant",
    "message_type": "USER_INPUT", 
    "message_id": "msg_123",
    "execution_context": "playbook_main",
    "correlation_id": "exec_456"
})
```

#### 2. User Interface Logging
**Purpose**: User-facing output in CLI and web applications  
**Audience**: Playbook authors and end users  
**Format**: Rich formatted text (CLI) / JSON events (web)  
**Output**: Console/WebSocket (clean, actionable)  

```python
# Example: CLI user feedback
user_console.agent_message("assistant", "I'll help you analyze the data...")
user_console.success("Playbook execution completed successfully")
user_console.error("Failed to connect to API", details="Check your API key")

# Example: Web events
web_logger.emit_event("agent_streaming_update", {
    "agent_name": "assistant",
    "content": "Analyzing...",
    "timestamp": datetime.utcnow().isoformat()
})
```

#### 3. System Operations Logging
**Purpose**: Production monitoring, alerting, and audit trails  
**Audience**: Operations teams and monitoring systems  
**Format**: Structured JSON with metrics  
**Output**: File + external systems (e.g., ELK, DataDog)  

```python
# Example: Production system logging
ops_logger.info("Playbook execution completed", extra={
    "execution_id": "exec_789",
    "duration_ms": 2345,
    "agents_count": 3,
    "messages_processed": 47,
    "memory_peak_mb": 128,
    "success": True
})
```

### Core Components Architecture

#### 1. Logging Configuration System
```
src/playbooks/logging/
├── config.py              # Central configuration management
├── formatters.py          # JSON, structured, and rich formatters  
├── handlers.py            # File, console, WebSocket handlers
└── context.py             # Context management and correlation IDs
```

#### 2. Logger Factories
```
src/playbooks/logging/
├── framework_logger.py    # Framework development logging
├── user_console.py        # User-facing output (CLI)
├── web_events.py          # Web application event logging
└── operations_logger.py   # Production operations logging
```

#### 3. Integration Layer
```
src/playbooks/logging/
├── middleware.py          # Async context propagation
├── performance.py         # Performance monitoring integration
└── correlation.py         # Request/execution tracing
```

### Detailed Component Specifications

#### Framework Logger (`framework_logger.py`)
```python
class FrameworkLogger:
    """Structured logging for Playbooks framework development."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(f"playbooks.framework.{name}")
        self.context = CorrelationContext()
    
    def with_agent_context(self, agent_id: str, agent_type: str):
        """Return logger with agent context."""
        return self.with_context(agent_id=agent_id, agent_type=agent_type)
    
    def with_execution_context(self, execution_id: str, playbook_path: str):
        """Return logger with execution context."""
        return self.with_context(execution_id=execution_id, playbook_path=playbook_path)
    
    def performance_timer(self, operation: str):
        """Context manager for operation timing."""
        return PerformanceTimer(self, operation)
    
    # Standard log methods with automatic context injection
    def debug(self, msg: str, **kwargs): ...
    def info(self, msg: str, **kwargs): ...
    def error(self, msg: str, **kwargs): ...
```

#### User Console (`user_console.py`)
```python
class UserConsole:
    """Rich user-facing output for CLI applications."""
    
    def __init__(self, rich_console: Console = None):
        self.console = rich_console or Console()
        self.session_log = SessionLog()
    
    def agent_message(self, agent_name: str, content: str, streaming: bool = False):
        """Display agent message with rich formatting."""
        if streaming:
            self.console.print(f"\n[green]{agent_name}:[/green] ", end="")
        else:
            self.console.print(f"\n[green]{agent_name}:[/green] {content}")
        
        self.session_log.append(content, level=SessionLogItemLevel.AGENT_MESSAGE)
    
    def system_status(self, status: str, details: str = None):
        """Display system status updates."""
        self.console.print(f"[blue]ℹ[/blue] {status}")
        if details:
            self.console.print(f"[dim]{details}[/dim]")
    
    def success(self, message: str):
        """Display success message."""
        self.console.print(f"[green]✓[/green] {message}")
    
    def error(self, message: str, details: str = None, show_help: bool = True):
        """Display error with optional details and help."""
        self.console.print(f"[red]✗[/red] {message}")
        if details:
            self.console.print(f"[dim red]{details}[/dim red]")
        if show_help:
            self.console.print("[dim yellow]💡 Use --verbose for detailed logs[/dim yellow]")
    
    def progress_context(self, description: str):
        """Context manager for progress indication."""
        return ProgressContext(self.console, description)
```

#### Web Events Logger (`web_events.py`)
```python
class WebEventsLogger:
    """WebSocket event logging for web applications."""
    
    def __init__(self, websocket_manager: WebSocketManager):
        self.ws_manager = websocket_manager
        self.framework_logger = get_framework_logger("web_events")
    
    async def emit_event(self, event_type: EventType, data: Dict[str, Any]):
        """Emit event to WebSocket clients and log for debugging."""
        event = WebEvent(
            type=event_type,
            data=data,
            timestamp=datetime.utcnow(),
            correlation_id=get_correlation_id()
        )
        
        # Send to WebSocket clients
        await self.ws_manager.broadcast(event.to_dict())
        
        # Log for framework debugging
        self.framework_logger.debug("Web event emitted", extra={
            "event_type": event_type.value,
            "data_keys": list(data.keys()),
            "client_count": len(self.ws_manager.clients)
        })
    
    async def agent_streaming_update(self, agent_name: str, content: str):
        """Specialized method for agent streaming."""
        await self.emit_event(EventType.AGENT_STREAMING_UPDATE, {
            "agent_name": agent_name,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
```

#### Operations Logger (`operations_logger.py`)
```python
class OperationsLogger:
    """Production operations and monitoring logging."""
    
    def __init__(self):
        self.logger = logging.getLogger("playbooks.operations")
        self.metrics_collector = MetricsCollector()
    
    def execution_started(self, execution_id: str, playbook_paths: List[str]):
        """Log execution start with context."""
        self.logger.info("Playbook execution started", extra={
            "execution_id": execution_id,
            "playbook_count": len(playbook_paths),
            "playbook_paths": playbook_paths,
            "start_time": datetime.utcnow().isoformat(),
            "event_type": "execution_lifecycle"
        })
    
    def execution_completed(self, execution_id: str, duration_ms: float, 
                          success: bool, metrics: Dict[str, Any]):
        """Log execution completion with performance metrics."""
        self.logger.info("Playbook execution completed", extra={
            "execution_id": execution_id,
            "duration_ms": duration_ms,
            "success": success,
            "agents_spawned": metrics.get("agents_spawned", 0),
            "messages_processed": metrics.get("messages_processed", 0),
            "memory_peak_mb": metrics.get("memory_peak_mb", 0),
            "event_type": "execution_lifecycle"
        })
        
        # Send metrics to monitoring system
        self.metrics_collector.record_execution(execution_id, duration_ms, success)
    
    def agent_error(self, agent_id: str, error: Exception, context: Dict[str, Any]):
        """Log agent errors with full context."""
        self.logger.error("Agent execution error", extra={
            "agent_id": agent_id,
            "agent_type": context.get("agent_type"),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "execution_context": context,
            "stack_trace": traceback.format_exc(),
            "event_type": "agent_error"
        }, exc_info=error)
```

### Configuration System

#### Environment-Based Configuration
```bash
# .env configuration
# Framework Debug Logging
PLAYBOOKS_LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR
PLAYBOOKS_DEBUG_ENABLED=false              # Enable framework debug logging
PLAYBOOKS_LOG_FILE=logs/playbooks.log      # Framework log file
PLAYBOOKS_STRUCTURED_LOGS=true             # JSON format for logs

# User Interface
PLAYBOOKS_CONSOLE_OUTPUT=true              # CLI console output
PLAYBOOKS_RICH_FORMATTING=true             # Rich text formatting
PLAYBOOKS_SESSION_LOG_ENABLED=true         # Session logging

# Operations & Monitoring
PLAYBOOKS_OPERATIONS_LOG_FILE=logs/ops.log # Operations log file
PLAYBOOKS_METRICS_ENABLED=true             # Performance metrics collection
PLAYBOOKS_CORRELATION_IDS=true             # Request tracing

# Web Application
PLAYBOOKS_WEB_EVENTS_LOG=true              # WebSocket event logging
PLAYBOOKS_WEB_DEBUG_ENABLED=false          # Web framework debugging
```

#### Programmatic Configuration
```python
# config.py
class LoggingConfig:
    """Central logging configuration for Playbooks framework."""
    
    @classmethod
    def setup_development(cls):
        """Development environment with full debugging."""
        setup_logging(
            framework_debug=True,
            console_output=True,
            rich_formatting=True,
            log_level="DEBUG",
            structured_logs=True
        )
    
    @classmethod  
    def setup_production(cls):
        """Production environment optimized for performance."""
        setup_logging(
            framework_debug=False,
            console_output=False,
            log_level="INFO",
            structured_logs=True,
            operations_logging=True,
            metrics_enabled=True
        )
    
    @classmethod
    def setup_cli(cls):
        """CLI application with user-friendly output."""
        setup_logging(
            framework_debug=False,
            console_output=True,
            rich_formatting=True,
            log_level="WARNING",  # Minimal framework noise
            user_console=True
        )
```

## Implementation Context Mapping

### CLI Applications (agent_chat.py)

#### Current State
```python
# ❌ Mixed output strategies
console.print(f"\n[green]{agent_name}:[/green] ", end="")  # User output
print(f"[DEBUG] Processing message...")                     # Debug info (problematic)
```

#### Proposed Implementation
```python
# ✅ Separated concerns
class AgentChatApp:
    def __init__(self):
        self.user_console = UserConsole()
        self.framework_logger = get_framework_logger("agent_chat")
    
    async def display_agent_message(self, agent_name: str, content: str):
        # User-facing output
        self.user_console.agent_message(agent_name, content, streaming=True)
        
        # Framework debugging (only when enabled)
        self.framework_logger.debug("Agent message displayed", extra={
            "agent_name": agent_name,
            "content_length": len(content),
            "display_mode": "streaming"
        })
    
    async def handle_error(self, error: Exception):
        # User-facing error
        self.user_console.error(
            message="Failed to process your request",
            details=str(error),
            show_help=True
        )
        
        # Framework debugging
        self.framework_logger.error("Agent chat error", extra={
            "error_type": type(error).__name__,
            "user_context": self.get_user_context()
        }, exc_info=error)
```

### Web Applications (web_server.py)

#### Current State
```python
# ❌ Limited logging for WebSocket events
# No structured logging for debugging
```

#### Proposed Implementation
```python
class PlaybooksWebServer:
    def __init__(self):
        self.web_events = WebEventsLogger(self.websocket_manager)
        self.framework_logger = get_framework_logger("web_server")
        self.ops_logger = get_operations_logger()
    
    async def handle_websocket_connection(self, websocket, path):
        client_id = str(uuid.uuid4())
        
        # Framework debugging
        self.framework_logger.info("WebSocket connection established", extra={
            "client_id": client_id,
            "path": path,
            "remote_addr": websocket.remote_address
        })
        
        # User-facing event
        await self.web_events.emit_event(EventType.CONNECTION_ESTABLISHED, {
            "client_id": client_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Operations logging
        self.ops_logger.info("Client connected", extra={
            "client_id": client_id,
            "connection_type": "websocket",
            "event_type": "client_lifecycle"
        })
    
    async def broadcast_agent_message(self, agent_name: str, content: str):
        # WebSocket event for clients
        await self.web_events.agent_streaming_update(agent_name, content)
        
        # Framework debugging
        self.framework_logger.debug("Agent message broadcasted", extra={
            "agent_name": agent_name,
            "content_length": len(content),
            "active_clients": len(self.websocket_manager.clients)
        })
```

### Framework Internals

#### Agent System Logging
```python
class BaseAgent:
    def __init__(self, agent_id: str, agent_type: str):
        self.logger = get_framework_logger("agents").with_agent_context(
            agent_id=agent_id,
            agent_type=agent_type
        )
    
    async def process_message(self, message: Message):
        # Framework debugging with rich context
        self.logger.debug("Message processing started", extra={
            "message_type": message.type.value,
            "message_id": message.id,
            "sender": message.sender,
            "processing_queue_size": len(self._message_buffer)
        })
        
        with self.logger.performance_timer("message_processing"):
            try:
                result = await self._process_message_impl(message)
                
                self.logger.info("Message processed successfully", extra={
                    "message_id": message.id,
                    "processing_time_ms": self.logger.get_last_timer_duration(),
                    "result_type": type(result).__name__
                })
                
                return result
                
            except Exception as e:
                self.logger.error("Message processing failed", extra={
                    "message_id": message.id,
                    "error_context": {
                        "message_content": message.content[:100],  # Truncated
                        "agent_state": self.get_debug_state()
                    }
                }, exc_info=e)
                raise
```

#### Program Execution Logging
```python
class Program:
    def __init__(self):
        self.framework_logger = get_framework_logger("program")
        self.ops_logger = get_operations_logger()
    
    async def run_till_exit(self):
        execution_id = str(uuid.uuid4())
        
        with self.framework_logger.with_execution_context(
            execution_id=execution_id,
            playbook_paths=self.playbook_paths
        ):
            # Operations logging
            self.ops_logger.execution_started(execution_id, self.playbook_paths)
            
            start_time = time.time()
            success = False
            
            try:
                self.framework_logger.info("Program execution started")
                
                # Execute with performance monitoring
                await self._execute_program()
                
                success = True
                self.framework_logger.info("Program execution completed successfully")
                
            except Exception as e:
                self.framework_logger.error("Program execution failed", exc_info=e)
                raise
                
            finally:
                duration_ms = (time.time() - start_time) * 1000
                metrics = self._collect_execution_metrics()
                
                self.ops_logger.execution_completed(
                    execution_id, duration_ms, success, metrics
                )
```

## Migration Strategy

### Phase 1: Infrastructure Setup (Week 1)
1. **Create logging package structure**
   - Implement core configuration system
   - Build logger factories
   - Set up environment-based configuration

2. **Establish testing framework**
   - Unit tests for logging components
   - Performance benchmarks
   - Configuration validation

### Phase 2: Framework Core Migration (Week 2)
1. **Migrate debug infrastructure**
   - Replace print statements in `/debug/` modules
   - Implement structured debugging for debug_handler.py
   - Update debug server logging

2. **Update core execution engine**
   - Add framework logging to Program class
   - Instrument agent lifecycle logging
   - Add performance monitoring hooks

### Phase 3: Application Layer Migration (Week 3)
1. **Update CLI applications**
   - Migrate agent_chat.py to use UserConsole
   - Separate user output from debug information
   - Implement session logging

2. **Update web applications**  
   - Implement WebEventsLogger for web_server.py
   - Add WebSocket event logging
   - Integrate with existing streaming functionality

### Phase 4: Operations & Polish (Week 4)
1. **Production readiness**
   - Add operations logging and metrics
   - Implement correlation ID tracking
   - Set up monitoring integration points

2. **Documentation and examples**
   - Update developer documentation
   - Create logging best practices guide
   - Provide configuration examples

3. **Performance validation**
   - Benchmark logging overhead
   - Optimize for production workloads
   - Validate memory usage

## Success Metrics & Validation

### Development Experience Metrics
- **Debug Time Reduction**: 50% faster issue resolution with structured logs
- **Context Completeness**: 100% of critical operations have correlation IDs
- **Log Signal-to-Noise**: 90% of logs provide actionable information

### User Experience Metrics  
- **Output Clarity**: Clean separation of user output vs system information
- **Error Actionability**: 100% of user-facing errors include actionable guidance
- **Performance Impact**: <5ms logging overhead per operation

### Operations Metrics
- **Observability Coverage**: 100% of critical paths have structured logging
- **Alert Reliability**: <5% false positive rate on log-based alerts
- **Troubleshooting Efficiency**: 75% faster incident resolution

### Code Quality Metrics
- **Pattern Consistency**: 100% adoption of logging guidelines in new code
- **Legacy Cleanup**: 0 remaining print statements in production code paths
- **Test Coverage**: 95% coverage of logging functionality

## Risk Analysis & Mitigation

### Technical Risks

**Risk**: Performance overhead from structured logging  
**Mitigation**: Lazy evaluation, configurable levels, async logging where appropriate

**Risk**: Complex configuration leading to misconfiguration  
**Mitigation**: Sensible defaults, validation, environment-specific presets

**Risk**: Breaking changes during migration  
**Mitigation**: Phased rollout, backward compatibility layer, comprehensive testing

### Adoption Risks

**Risk**: Developer resistance to new patterns  
**Mitigation**: Clear documentation, examples, gradual migration, tooling support

**Risk**: Inconsistent usage across team  
**Mitigation**: Code review guidelines, linting rules, automated checks

## Appendix

### Configuration Reference

#### Complete Environment Variables
```bash
# Framework Logging
PLAYBOOKS_LOG_LEVEL=INFO
PLAYBOOKS_DEBUG_ENABLED=false
PLAYBOOKS_LOG_FILE=logs/playbooks.log
PLAYBOOKS_STRUCTURED_LOGS=true
PLAYBOOKS_ASYNC_LOGGING=false

# User Interface  
PLAYBOOKS_CONSOLE_OUTPUT=true
PLAYBOOKS_RICH_FORMATTING=true
PLAYBOOKS_SESSION_LOG_ENABLED=true
PLAYBOOKS_SESSION_LOG_FILE=logs/session.log

# Operations & Monitoring
PLAYBOOKS_OPERATIONS_LOG_FILE=logs/operations.log
PLAYBOOKS_METRICS_ENABLED=true
PLAYBOOKS_CORRELATION_IDS=true
PLAYBOOKS_PERFORMANCE_MONITORING=true

# Web Application
PLAYBOOKS_WEB_EVENTS_LOG=true
PLAYBOOKS_WEB_DEBUG_ENABLED=false
PLAYBOOKS_WEBSOCKET_LOG_LEVEL=INFO

# External Integrations
PLAYBOOKS_LANGFUSE_LOGGING=false
PLAYBOOKS_EXTERNAL_LOG_ENDPOINT=""
PLAYBOOKS_LOG_SHIPPER_ENABLED=false
```

#### Logger Hierarchy
```
playbooks/                          # Root logger
├── framework/                      # Framework development logging
│   ├── agents/                     # Agent system logging
│   ├── execution/                  # Execution engine logging  
│   ├── compilation/                # Compiler logging
│   └── transport/                  # Communication logging
├── applications/                   # Application-specific logging
│   ├── cli/                        # CLI application logging
│   ├── web/                        # Web application logging
│   └── debug/                      # Debug tooling logging
└── operations/                     # Production operations logging
    ├── performance/                # Performance metrics
    ├── security/                   # Security events
    └── lifecycle/                  # System lifecycle events
```

### Performance Benchmarks

#### Target Performance Characteristics
- **Framework Debug Logging**: <1ms per log entry
- **User Console Output**: <5ms per message (including rich formatting)
- **Web Event Emission**: <2ms per event (excluding WebSocket transmission)
- **Operations Logging**: <3ms per entry (including metrics collection)
- **Memory Overhead**: <50MB for logging infrastructure
- **Log File I/O**: Non-blocking with configurable buffer sizes

#### Load Testing Scenarios
- **High-Frequency Debugging**: 1000 debug entries/second
- **Agent Message Streaming**: 100 concurrent streaming sessions
- **Web Event Broadcasting**: 500 concurrent WebSocket clients
- **Production Logging**: 24/7 operations with log rotation

This comprehensive logging architecture provides the foundation for scalable, maintainable, and observable Playbooks applications while maintaining excellent developer and user experiences across all execution contexts.