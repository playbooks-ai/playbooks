# Variable Capture Test Suite

This directory contains comprehensive unit tests for local variable capture in the Playbooks system.

## Overview

Local variables from LLM-generated Python blocks are captured and stored in `CallStackFrame.locals` to persist across multiple LLM calls within the same playbook execution. This enables variables to survive yield points (e.g., waiting for user input) and be available when execution resumes.

## Test Files

### 1. `test_local_variable_capture.py`
Tests basic variable capture mechanisms.

**Key Findings:**
- `PythonExecutor` does NOT capture local variables (wraps code in a function)
- `StreamingPythonExecutor` DOES capture local variables (actual playbook execution)
- Variables captured include: simple types, collections, functions
- Local and state variables can coexist
- Playbook arguments are initialized in `frame.locals`

**Test Coverage:**
- Simple variable capture
- Multiple variables
- Arithmetic operations
- Local + state variable interaction
- Playbook arguments merging
- List comprehensions (loops have limitations with exec)

### 2. `test_variable_persistence_across_llm_calls.py`
Tests variable persistence across multiple execution calls (simulating yield/resume).

**Key Findings:**
- Variables persist in `CallStackFrame.locals` after execution
- Frame stays on stack when playbook yields
- Subsequent executors can access previously defined variables
- Variables accumulate across multiple calls
- Both local and state variables persist independently

**Test Coverage:**
- Variable persistence after execution
- Frame survival during yield simulation
- Variable availability across calls
- Multiple LLM calls accumulating locals
- Playbook args + locals persistence
- Variable modification across calls
- Local/state variable independence
- Building collections incrementally

### 3. `test_streaming_variable_capture.py`
Tests specific to `StreamingPythonExecutor` (actual playbook execution).

**Key Findings:**
- Streaming execution captures variables incrementally
- Variables from early chunks available in later chunks
- Both sync and async statements capture correctly
- Frame.locals updated as each statement executes

**Test Coverage:**
- Simple local capture in streaming mode
- Multiple statements
- Async/await variable capture
- Sync and async mixed
- Variables available across chunks
- Incremental frame.locals updates
- Playbook args with streaming
- Conditionals, functions, collections
- Partial chunk handling (split tokens)

### 4. `test_interpreter_prompt.py` (extended)
Tests that local variables appear correctly in the LLM context prefix.

**Key Findings:**
- `InterpreterPrompt._build_context_prefix()` reads `frame.locals`
- Local variables displayed without `self.state` prefix
- State variables displayed with `self.state` prefix
- Proper literal vs non-literal formatting

**Test Coverage:**
- Simple locals in context
- Locals and state together
- Playbook args as locals
- Formatting (literals vs placeholders)
- Empty frame handling

### 5. `test_variable_capture_e2e.py` (integration)
End-to-end tests using actual playbooks.

**Coverage:**
- Simple playbooks with local variables
- Yield points preserving locals
- Nested playbook calls (separate frames)
- Playbook args and locals interaction
- Complex variable flows
- Loops, conditionals
- State and local persistence

## Architecture Summary

### Variable Storage
```
CallStackFrame.locals: Dict[str, Any]
```

### Within a Single LLM Call

**StreamingPythonExecutor:**
1. Playbook args initialized in `frame.locals` (line 88)
2. For sync statements: `exec(code, namespace, frame_locals)` directly updates `frame_locals` (line 232-236)
3. For async statements: wrapped in function, locals extracted back to `frame_locals` (line 240-282)

### Across Multiple LLM Calls

**Frame Persistence:**
- `CallStackFrame` remains on stack when playbook yields
- Frame persists until playbook completes

**Context Building:**
- `InterpreterPrompt._build_context_prefix()` reads `frame.locals` (line 199-205)
- Shows LLM what local variables are available

**Execution Resumption:**
- New executor merges `frame.locals` into execution namespace
- Variables from previous calls available

## Limitations

1. **PythonExecutor:** Does not capture locals (wraps code in function)
2. **Loop mutations:** `+=` inside loops may not work due to exec() scoping
3. **Workarounds:** Use list comprehensions, `sum()`, or assignment instead of mutations

## Running the Tests

```bash
# Run all variable capture tests
pytest tests/unit/execution/test_local_variable_capture.py -v
pytest tests/unit/execution/test_variable_persistence_across_llm_calls.py -v
pytest tests/unit/execution/test_streaming_variable_capture.py -v
pytest tests/unit/execution/test_interpreter_prompt.py::TestContextPrefixLocalVariables -v

# Run integration tests
pytest tests/integration/test_variable_capture_e2e.py -v

# Run all together
pytest tests/unit/execution/test_*variable*.py tests/integration/test_variable_capture_e2e.py -v
```

## Implementation References

- **Variable capture in StreamingPythonExecutor:**
  - `src/playbooks/execution/streaming_python_executor.py:88` - Init frame locals
  - `src/playbooks/execution/streaming_python_executor.py:232-236` - Sync execution
  - `src/playbooks/execution/streaming_python_executor.py:240-282` - Async with capture

- **Context building:**
  - `src/playbooks/execution/interpreter_prompt.py:199-205` - Display locals

- **Frame structure:**
  - `src/playbooks/state/call_stack.py:143` - `CallStackFrame.locals` definition
