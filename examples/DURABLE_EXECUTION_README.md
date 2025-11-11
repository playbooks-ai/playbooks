# Durable Execution Example

This example demonstrates Playbooks' durable execution capability.

## What is Durable Execution?

Durable execution allows playbooks to:
- **Save checkpoints** at every `await` statement
- **Resume execution** after crashes, restarts, or failures
- **Continue from exact point** without re-running completed steps

## Quick Start

### 1. Enable Durability

In `playbooks.toml`:

```toml
[durability]
enabled = true
storage_path = ".checkpoints"
```

### 2. Run Your Playbook

```bash
python examples/durable_execution_example.py
```

### 3. Simulate Crash & Resume

```python
# Your playbook runs and checkpoints automatically
# If it crashes, just restart:

from playbooks.checkpoints import CheckpointManager, RecoveryCoordinator

coordinator = RecoveryCoordinator(manager)
if await coordinator.can_recover():
    checkpoint = await manager.get_latest_checkpoint()
    await coordinator.recover_execution_state(agent)
    
    executor = await StreamingPythonExecutor.resume_from_checkpoint(
        agent, checkpoint
    )
```

## The Magic

### Automatic Checkpointing

```python
@playbook
async def MyWorkflow():
    # Each await is a checkpoint
    data = await FetchData()       # ✅ Checkpoint 1
    result = await Process(data)   # ✅ Checkpoint 2
    await Save(result)             # ✅ Checkpoint 3
    return result
```

### After Crash

If crash occurs after Checkpoint 2:
- ✅ `data` and `result` variables restored
- ✅ Execution resumes at: `await Save(result)`
- ✅ Workflow completes successfully

## Features Demonstrated

- ✅ Automatic checkpointing at await statements
- ✅ State restoration (variables, call stack)
- ✅ Execution continuation from checkpoint
- ✅ Filesystem-based storage
- ✅ Recovery API

## Architecture

```
Execution Flow with Checkpointing:

1. Start execution
2. Execute: await FetchData()
   → Save checkpoint ✅
3. Execute: await Process(data)
   → Save checkpoint ✅
4. 💥 CRASH
5. Restart process
6. Load checkpoint
7. Restore state
8. Resume: await Save(result)
   → Continues normally ✅
```

## Configuration

See `playbooks.toml`:

```toml
[durability]
enabled = true                  # Enable/disable
storage_path = ".checkpoints"   # Where to store checkpoints
max_checkpoint_size_mb = 10     # Size limit
keep_last_n = 10                # Retention policy
```

## Documentation

- **User Guide**: `docs/guides/durable-execution.md`
- **Implementation**: `docs/durability-implementation-status.md`
- **Visual Demo**: `CHECKPOINT_RESUME_DEMO.md`

## Learn More

- Checkpoint storage backends
- Recovery coordinator API
- Plugin architecture for enterprise
- PostgreSQL/Redis storage (enterprise)

See the main documentation for complete details!

