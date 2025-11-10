# Durable Execution

Playbooks provides durable execution through automatic checkpointing at natural suspension points (await statements). This allows playbooks to recover from crashes, process restarts, or infrastructure failures.

## Overview

**Durable execution** ensures that playbook workflows can resume from the last successful checkpoint rather than restarting from the beginning. This is critical for:

- Long-running workflows
- Production deployments
- Multi-step processes with expensive operations
- Workflows involving external API calls

## How It Works

Playbooks automatically checkpoints execution at every `await` statement in LLM-generated code. Each checkpoint captures:

- **Execution state**: Variables, call stack, agent state
- **Namespace**: Python variables and their values  
- **Metadata**: Statement executed, timestamp, counter

### Checkpoint Boundaries

Checkpoints occur at:
- ✅ `await Say()` calls
- ✅ `await Yld()` calls
- ✅ `await OtherPlaybook()` calls
- ✅ Any top-level `await` in CustomPythonPlaybook
- ❌ Awaits inside loops (see caveat below)

## Configuration

### Enable Durability

In `playbooks.toml`:

```toml
[durability]
enabled = true
storage_type = "filesystem"
storage_path = ".checkpoints"
max_checkpoint_size_mb = 10
keep_last_n = 10
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `enabled` | `false` | Enable/disable checkpointing |
| `storage_type` | `"filesystem"` | Storage backend (`"filesystem"` in OSS) |
| `storage_path` | `".checkpoints"` | Directory for checkpoint files |
| `max_checkpoint_size_mb` | `10` | Maximum checkpoint size in MB |
| `keep_last_n` | `10` | Number of recent checkpoints to retain |

## Storage Backends

### Filesystem (OSS)

Suitable for:
- Development and testing
- Single-node deployments
- Local file system availability

Limitations:
- Single node only (no distributed coordination)
- File system dependent
- Limited to 10MB per checkpoint

### Enterprise Backends

The `playbooks[enterprise]` package provides:
- **PostgreSQL**: Multi-node, persistent storage
- **Redis**: Fast, distributed checkpoints
- **Advanced features**: Compression, retention policies, monitoring

## Usage Examples

### Basic Usage

Durability is transparent when enabled:

```python
# playbooks automatically checkpoints at await statements

@playbook
async def process_orders():
    orders = await fetch_orders()  # ✅ Checkpoint saved
    
    for order in orders:
        result = await process_order(order)  # ⚠️ See caveat below
        await save_result(result)  # ⚠️ See caveat below
    
    await send_summary()  # ✅ Checkpoint saved
```

### Manual Checkpointing in Loops

For long-running loops, add manual checkpoints:

```python
@playbook  
async def process_many_items(items):
    for i, item in enumerate(items):
        result = await process_item(item)
        
        # Manual checkpoint every 100 items
        if i % 100 == 0:
            await __checkpoint__(locals())
```

Note: Manual checkpointing API is planned for future release.

### Recovery

Recovery is automatic on restart:

```python
from playbooks.checkpoints import CheckpointManager, RecoveryCoordinator

# Check if recovery is possible
manager = CheckpointManager(execution_id=agent.id, provider=provider)
coordinator = RecoveryCoordinator(manager)

if await coordinator.can_recover():
    info = await coordinator.get_recovery_info()
    print(f"Resuming from: {info['statement']}")
    
    # Restore state
    await coordinator.recover_execution_state(agent)
```

## Caveat: Loops and Checkpointing

**Important**: Awaits inside `for` and `while` loops are not individually checkpointed in the baseline implementation.

### Why?

Checkpointing every loop iteration would:
- Create excessive checkpoint overhead
- Generate thousands of checkpoint files
- Slow down execution significantly

### Workaround

For loops processing many items, use batching or manual checkpoints:

```python
# Instead of:
for item in large_list:  # 1000s of items
    await process(item)  # Would checkpoint 1000s of times

# Do this:
for batch in chunks(large_list, 100):  # Process in batches
    results = []
    for item in batch:
        result = await process(item)
        results.append(result)
    await save_batch(results)  # Checkpoint once per batch
```

## Checkpoint Storage

### File Structure

Checkpoints are stored in a directory structure:

```
.checkpoints/
    {agent_id}/
        {agent_id}_ckpt_1.pkl
        {agent_id}_ckpt_2.pkl
        {agent_id}_ckpt_3.pkl
        ...
```

### Checkpoint Contents

Each checkpoint file contains:

```python
{
    "checkpoint_id": "agent_123_ckpt_5",
    "execution_state": {
        "variables": {"$x": 10, "$result": "..."},
        "call_stack": [...],
        "agents": [...]
    },
    "namespace": {
        "x": 10,
        "result": "..."
    },
    "metadata": {
        "statement": "await Say('user', 'Hello')",
        "counter": 5,
        "timestamp": 1234567890.123,
        "execution_id": "agent_123"
    }
}
```

### Cleanup

Old checkpoints are automatically cleaned up based on `keep_last_n` setting. Manual cleanup:

```python
deleted = await manager.cleanup_old_checkpoints(keep_last_n=5)
print(f"Deleted {deleted} old checkpoints")
```

## Extension: Enterprise Features

Install enterprise package:

```bash
pip install playbooks[enterprise]
```

Configure PostgreSQL storage in `playbooks.toml`:

```toml
[durability]
enabled = true
storage_type = "postgres"

[durability.config]
connection_string = "postgresql://user:pass@localhost/playbooks"
max_checkpoint_size_mb = 50
compression = true
```

Enterprise features:
- Multi-node coordination
- Distributed recovery
- Advanced compression
- Retention policies
- Performance monitoring
- High availability

## Best Practices

### 1. Enable for Production

Always enable durability for production workflows:

```toml
[durability]
enabled = true  # In production
```

### 2. Monitor Checkpoint Size

Check checkpoint sizes to avoid storage issues:

```python
checkpoints = await provider.list_checkpoints(execution_id)
for ckpt_id in checkpoints:
    data = await provider.load_checkpoint(ckpt_id)
    size = len(pickle.dumps(data))
    print(f"{ckpt_id}: {size / 1024 / 1024:.2f} MB")
```

### 3. Tune Retention

Adjust `keep_last_n` based on workflow length:

```toml
[durability]
keep_last_n = 20  # For longer workflows
```

### 4. Handle Non-Serializable Objects

Some objects can't be checkpointed (e.g., file handles, network connections):

```python
# Avoid storing in variables that get checkpointed
with open('file.txt') as f:  # File handle not checkpointed
    content = f.read()
    # Store content, not file handle
    result = await process(content)
```

## Troubleshooting

### Checkpoint Size Exceeded

```
ValueError: Checkpoint exceeds size limit: 12.5MB > 10MB
```

**Solution**: Increase `max_checkpoint_size_mb` or reduce variable sizes.

### Checkpoints Not Created

**Check**: Is durability enabled in config?

```toml
[durability]
enabled = true  # Must be true
```

### Recovery Fails

**Check**: Do checkpoint files exist?

```bash
ls -la .checkpoints/*/
```

## See Also

- [Configuration](../configuration.md)
- [CustomPythonPlaybooks](custom-python-playbooks.md)
- [Enterprise Features](enterprise-features.md) (requires playbooks[enterprise])

