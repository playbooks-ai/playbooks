# Async Testing Guide for Playbooks Framework

This guide provides comprehensive patterns and best practices for testing async components in the Playbooks framework.

## Overview

The Playbooks framework uses pure asyncio throughout. Testing async code requires special considerations for:
- Proper async test setup
- Cancellation handling
- Timing and race conditions
- Resource cleanup
- Error isolation

## Test Categories

### 1. Unit Tests
**Purpose**: Test individual async components in isolation
**Location**: `tests/unit/`
**Pattern**: Test single class/function behavior

```python
@pytest.mark.asyncio
class TestAsyncComponent:
    async def test_basic_operation(self):
        component = AsyncComponent()
        result = await component.operation()
        assert result == expected_value
```

### 2. Integration Tests
**Purpose**: Test interaction between async components
**Location**: `tests/integration/`
**Pattern**: Test component collaboration

```python
@pytest.mark.asyncio
async def test_component_integration():
    bus = EventBus("test")
    queue = AsyncMessageQueue()
    
    # Test interaction
    async with bus, queue:
        # Test logic here
        pass
```

### 3. Performance Tests
**Purpose**: Measure async performance characteristics
**Location**: `tests/benchmarks/`
**Pattern**: Time operations and measure throughput

```python
async def test_performance():
    start_time = time.perf_counter()
    
    # Perform operations
    await component.bulk_operation(1000)
    
    elapsed = time.perf_counter() - start_time
    assert elapsed < target_time
```

### 4. Chaos Tests
**Purpose**: Test resilience under failure conditions
**Location**: `tests/chaos/`
**Pattern**: Inject random failures and verify graceful handling

```python
async def test_chaos_resilience():
    chaos = ChaosMonkey(failure_rate=0.1)
    
    async with chaos_test_context(chaos):
        # Operations that may randomly fail
        await component.operation_with_failures()
```

## Common Testing Patterns

### Pattern 1: Context Manager Testing

**Use Case**: Testing resource lifecycle

```python
@pytest.mark.asyncio
async def test_context_manager():
    async with AsyncComponent() as component:
        # Component is initialized
        assert component.is_active
        
        # Use component
        result = await component.operation()
        
    # Component is cleaned up
    assert component.is_closed
```

### Pattern 2: Exception Testing

**Use Case**: Testing error conditions

```python
@pytest.mark.asyncio
async def test_error_handling():
    component = AsyncComponent()
    
    # Test specific exception
    with pytest.raises(SpecificError, match="expected message"):
        await component.failing_operation()
        
    # Test cancellation
    task = asyncio.create_task(component.long_operation())
    await asyncio.sleep(0.01)  # Let it start
    task.cancel()
    
    with pytest.raises(asyncio.CancelledError):
        await task
```

### Pattern 3: Timeout Testing

**Use Case**: Testing operations under time constraints

```python
@pytest.mark.asyncio
async def test_timeout_behavior():
    component = AsyncComponent()
    
    # Test timeout
    start_time = time.time()
    with pytest.raises(asyncio.TimeoutError):
        await component.operation_with_timeout(timeout=0.1)
        
    elapsed = time.time() - start_time
    assert 0.09 <= elapsed <= 0.2  # Allow some tolerance
```

### Pattern 4: Concurrent Operations

**Use Case**: Testing thread safety and concurrent access

```python
@pytest.mark.asyncio
async def test_concurrent_access():
    component = AsyncComponent()
    results = []
    
    async def worker(worker_id: int):
        result = await component.operation(worker_id)
        results.append(result)
        
    # Run multiple workers concurrently
    workers = [worker(i) for i in range(10)]
    await asyncio.gather(*workers)
    
    # Verify results
    assert len(results) == 10
    assert len(set(results)) == 10  # All unique
```

### Pattern 5: Playbooks Async Functions

**Use Case**: Playbooksing async dependencies

```python
from unittest.mock import AsyncPlaybooks, patch

@pytest.mark.asyncio
async def test_with_playbooksed_dependency():
    playbooks_dependency = AsyncPlaybooks()
    playbooks_dependency.async_method.return_value = "playbooksed_result"
    
    with patch('module.dependency', playbooks_dependency):
        component = AsyncComponent()
        result = await component.operation_using_dependency()
        
    assert result == "processed_playbooksed_result"
    playbooks_dependency.async_method.assert_called_once()
```

### Pattern 6: Event Testing

**Use Case**: Testing event-driven components

```python
@pytest.mark.asyncio
async def test_event_handling():
    bus = EventBus("test")
    received_events = []
    
    def handler(event):
        received_events.append(event)
        
    bus.subscribe(TestEvent, handler)
    
    # Trigger event
    await bus.publish(TestEvent("test_data"))
    
    # Verify
    assert len(received_events) == 1
    assert received_events[0].data == "test_data"
```

### Pattern 7: Message Queue Testing

**Use Case**: Testing message passing

```python
@pytest.mark.asyncio
async def test_message_flow():
    queue = AsyncMessageQueue()
    
    # Producer task
    async def producer():
        for i in range(5):
            await queue.put(TestMessage(f"msg-{i}"))
            
    # Consumer task
    messages = []
    async def consumer():
        for _ in range(5):
            msg = await queue.get()
            messages.append(msg)
            
    # Run concurrently
    await asyncio.gather(producer(), consumer())
    
    # Verify order
    assert len(messages) == 5
    assert [m.content for m in messages] == [f"msg-{i}" for i in range(5)]
```

## Best Practices

### 1. Use pytest-asyncio

```python
# Mark async test functions
@pytest.mark.asyncio
async def test_async_function():
    pass

# Mark entire test class  
@pytest.mark.asyncio
class TestAsyncClass:
    pass
```

### 2. Proper Resource Cleanup

```python
@pytest.mark.asyncio
async def test_with_cleanup():
    component = None
    try:
        component = AsyncComponent()
        await component.initialize()
        
        # Test logic
        result = await component.operation()
        assert result is not None
        
    finally:
        if component:
            await component.cleanup()
```

### 3. Use Context Managers

```python
@pytest.mark.asyncio
async def test_with_context_manager():
    async with AsyncComponent() as component:
        # Automatic cleanup guaranteed
        result = await component.operation()
        assert result is not None
```

### 4. Test Both Success and Failure Paths

```python
@pytest.mark.asyncio
class TestOperationBehavior:
    async def test_success_path(self):
        # Test normal operation
        component = AsyncComponent()
        result = await component.operation("valid_input")
        assert result.success
        
    async def test_failure_path(self):
        # Test error conditions
        component = AsyncComponent()
        with pytest.raises(ValidationError):
            await component.operation("invalid_input")
```

### 5. Handle Timing Issues

```python
@pytest.mark.asyncio
async def test_with_proper_timing():
    component = AsyncComponent()
    
    # Start operation
    task = asyncio.create_task(component.slow_operation())
    
    # Give it time to start
    await asyncio.sleep(0.01)
    
    # Now test intermediate state
    assert component.is_running
    
    # Wait for completion
    result = await task
    assert result is not None
```

### 6. Use Fixtures for Common Setup

```python
@pytest.fixture
async def event_bus():
    async with EventBus("test-session") as bus:
        yield bus

@pytest.fixture
async def message_queue():
    async with AsyncMessageQueue() as queue:
        yield queue

@pytest.mark.asyncio
async def test_with_fixtures(event_bus, message_queue):
    # Use pre-configured components
    await event_bus.publish(TestEvent())
    await message_queue.put(TestMessage())
```

## Common Pitfalls

### 1. Forgetting `await`

```python
# Wrong - missing await
result = component.async_operation()

# Correct
result = await component.async_operation()
```

### 2. Not Handling CancelledError

```python
# Wrong - doesn't handle cancellation
async def operation():
    await long_running_task()
    cleanup()  # May not run if cancelled

# Correct - proper cancellation handling
async def operation():
    try:
        await long_running_task()
    finally:
        cleanup()  # Always runs
```

### 3. Race Conditions in Tests

```python
# Wrong - race condition
async def test_race_condition():
    component.start_background_task()
    assert component.task_completed  # May not be true yet

# Correct - wait for completion
async def test_no_race():
    await component.start_background_task()
    assert component.task_completed
```

### 4. Improper Timeout Testing

```python
# Wrong - doesn't account for test overhead
async def test_timeout():
    start = time.time()
    with pytest.raises(asyncio.TimeoutError):
        await component.operation(timeout=1.0)
    elapsed = time.time() - start
    assert elapsed == 1.0  # Too strict

# Correct - allows tolerance
async def test_timeout():
    start = time.time()
    with pytest.raises(asyncio.TimeoutError):
        await component.operation(timeout=1.0)
    elapsed = time.time() - start
    assert 0.9 <= elapsed <= 1.1  # Reasonable tolerance
```

## Debugging Async Tests

### 1. Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 2. Use asyncio Debug Mode

```python
import asyncio
asyncio.get_event_loop().set_debug(True)
```

### 3. Add Strategic Sleep Points

```python
# Add to understand timing
await asyncio.sleep(0.01)
print(f"State: {component.state}")
```

### 4. Use pytest Verbose Output

```bash
pytest -v -s test_file.py::test_function
```

## Performance Testing Guidelines

### 1. Measure What Matters

```python
@pytest.mark.asyncio
async def test_throughput():
    component = AsyncComponent()
    
    start_time = time.perf_counter()
    
    # Measure specific operation
    results = await asyncio.gather(*[
        component.operation(i) for i in range(1000)
    ])
    
    elapsed = time.perf_counter() - start_time
    throughput = len(results) / elapsed
    
    assert throughput > 100  # ops/second
```

### 2. Test Under Load

```python
@pytest.mark.asyncio
async def test_under_load():
    component = AsyncComponent()
    
    # Simulate high load
    tasks = [
        component.operation(i) for i in range(1000)
    ]
    
    # All should complete within reasonable time
    start_time = time.perf_counter()
    results = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start_time
    
    assert all(r.success for r in results)
    assert elapsed < 10.0  # Should finish in 10 seconds
```

### 3. Memory Usage Testing

```python
import psutil
import gc

@pytest.mark.asyncio
async def test_memory_usage():
    process = psutil.Process()
    
    initial_memory = process.memory_info().rss
    
    # Perform memory-intensive operations
    component = AsyncComponent()
    for i in range(1000):
        await component.memory_operation()
        
    # Force cleanup
    gc.collect()
    
    final_memory = process.memory_info().rss
    memory_growth = final_memory - initial_memory
    
    # Should not grow excessively
    assert memory_growth < 50 * 1024 * 1024  # 50MB limit
```

This testing guide provides a comprehensive foundation for testing async components in the Playbooks framework. Follow these patterns to ensure robust, reliable async code.