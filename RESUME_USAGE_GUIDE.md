# How to Resume from Checkpoint - Complete Guide

## Quick Answer

```bash
# Enable durability first
[durability]
enabled = true

# Run your playbook
playbooks run blah.pb

# If it crashes...

# Resume from last checkpoint
playbooks run blah.pb --resume
```

## Complete Walkthrough

### Step 1: Enable Durability

Create or edit `playbooks.toml`:

```toml
[durability]
enabled = true
storage_path = ".checkpoints"
max_checkpoint_size_mb = 10
keep_last_n = 10
```

### Step 2: Run Your Playbook (First Time)

```bash
playbooks run blah.pb
```

**What happens:**
- Playbook executes normally
- Checkpoint saved after each `await` statement
- Checkpoints stored in `.checkpoints/{agent_id}/`

### Step 3: Execution Gets Interrupted

Scenarios:
- 💥 Process crashes
- 🔌 Power failure
- ⏹️  User hits Ctrl+C
- 🐛 Unhandled exception
- 💻 Node failure

**Your checkpoints are safe on disk!**

### Step 4: Resume Execution

```bash
playbooks run blah.pb --resume
```

**What happens:**
1. Playbooks detects existing checkpoints
2. Loads latest checkpoint for each agent
3. Restores agent state (variables, call stack)
4. Resumes execution from exact checkpoint
5. Continues processing remaining code
6. Proceeds to next LLM calls

**Output:**
```
🔄 Found checkpoint for agent agent_123
   Checkpoint: agent_123_ckpt_7
   Last statement: data = await FetchData()...
✅ Resumed execution for agent agent_123
```

## Detailed Example

### Your Playbook (`blah.pb`)

```markdown
# MyAgent:AI

## ProcessOrders

```python
await Step("ProcessOrders:01:QUE")
await Say("user", "Starting order processing...")

await Step("ProcessOrders:02:ACT")
orders = await FetchOrders()  # ✅ Checkpoint 1

await Step("ProcessOrders:03:ACT") 
for order in orders:
    result = await ProcessOrder(order)  # ⚠️ Not checkpointed (loop)
    
batch_result = await SaveBatch(results)  # ✅ Checkpoint 2

await Step("ProcessOrders:04:ACT")
summary = await GenerateSummary(batch_result)  # ✅ Checkpoint 3

await Say("user", f"Complete! {summary}")
await Return(summary)
\```
```

### Execution Timeline

#### Run 1: Initial Execution

```bash
$ playbooks run blah.pb

Loading playbooks from: ['blah.pb']
Starting order processing...
# Executing...
# ✅ Checkpoint 1 saved (after FetchOrders)
# ✅ Checkpoint 2 saved (after SaveBatch)
# 💥 CRASH during GenerateSummary
```

**Checkpoints saved:**
- `.checkpoints/agent_123/agent_123_ckpt_1.pkl` ✅
- `.checkpoints/agent_123/agent_123_ckpt_2.pkl` ✅

#### Run 2: Resume

```bash
$ playbooks run blah.pb --resume

Loading playbooks from: ['blah.pb']
🔄 Found checkpoint for agent agent_123
   Checkpoint: agent_123_ckpt_2
   Last statement: batch_result = await SaveBatch(results)
✅ Resumed execution for agent agent_123

# Continues execution:
# ✅ Resumes at: summary = await GenerateSummary(batch_result)
# ✅ Checkpoint 3 saved
# ✅ Completes successfully!
Complete! Summary: ...
```

## Without --resume Flag

```bash
# Without --resume, execution starts from beginning
playbooks run blah.pb

# Re-executes everything from step 1
# Ignores existing checkpoints
```

## Checkpoint Management

### View Checkpoints

```bash
# List checkpoints
ls -la .checkpoints/*/

# Example output:
.checkpoints/agent_123/:
  agent_123_ckpt_1.pkl  (created 2025-11-09 17:15:30)
  agent_123_ckpt_2.pkl  (created 2025-11-09 17:15:45)
```

### Clear Checkpoints

```bash
# Remove all checkpoints (fresh start)
rm -rf .checkpoints/

# Remove checkpoints for specific agent
rm -rf .checkpoints/agent_123/
```

### Check Checkpoint Info

```python
from playbooks.checkpoints import FilesystemCheckpointProvider, CheckpointManager

provider = FilesystemCheckpointProvider()
manager = CheckpointManager(execution_id="agent_123", provider=provider)

checkpoints = await provider.list_checkpoints("agent_123")
print(f"Found {len(checkpoints)} checkpoints")

for ckpt_id in checkpoints:
    ckpt = await provider.load_checkpoint(ckpt_id)
    print(f"{ckpt_id}: {ckpt['metadata']['statement']}")
```

## Common Scenarios

### Scenario 1: Long-Running Workflow

```bash
# Start long workflow
playbooks run long_workflow.pb

# Runs for hours...
# 100 LLM calls, many await statements
# Checkpoints saved throughout

# 💥 Server crashes after 3 hours

# Resume from last checkpoint (within seconds!)
playbooks run long_workflow.pb --resume

# Continues from last successful await
# Only loses work since last checkpoint (< 1 minute typically)
```

### Scenario 2: Development/Testing

```bash
# Testing a complex playbook
playbooks run complex.pb

# Hits error halfway through
# Want to fix and resume

# Fix the issue in code
# Resume from last good checkpoint
playbooks run complex.pb --resume

# Continues from checkpoint, tests the fix
```

### Scenario 3: Production Deployment

```bash
# Production: Enable durability
[durability]
enabled = true
storage_path = "/var/lib/playbooks/checkpoints"

# Run with process supervision (systemd, supervisor, etc.)
playbooks run production.pb

# If process crashes, supervisor restarts:
playbooks run production.pb --resume

# Automatically resumes, minimal disruption
```

## Troubleshooting

### "Resume requested but durability not enabled"

```bash
# Error message:
⚠️  Resume requested but durability not enabled
   Set durability.enabled=true in playbooks.toml
```

**Solution:** Enable in `playbooks.toml`:
```toml
[durability]
enabled = true
```

### "No checkpoints found"

```bash
# Warning message:
⚠️  No checkpoints found for agent agent_123
```

**Reasons:**
1. First run (no checkpoints yet)
2. Checkpoints were cleared
3. Different execution ID
4. Wrong storage_path configured

**Solution:** Run without `--resume` first to create checkpoints.

### Resume Doesn't Continue

**Check:**
1. Is durability enabled? (`durability.enabled = true`)
2. Do checkpoint files exist? (`ls .checkpoints/*/`)
3. Is checkpoint path correct? (check `durability.storage_path`)

## Advanced Usage

### Programmatic Resume

```python
import asyncio
from playbooks import Playbooks
from playbooks.checkpoints import (
    FilesystemCheckpointProvider,
    CheckpointManager,
    RecoveryCoordinator
)
from playbooks.execution.streaming_python_executor import StreamingPythonExecutor

async def run_with_auto_resume(playbook_path: str):
    """Run playbook with automatic resume on failure."""
    
    playbooks = Playbooks([playbook_path])
    await playbooks.initialize()
    
    # Check for checkpoints
    for agent in playbooks.program.agents:
        provider = FilesystemCheckpointProvider()
        manager = CheckpointManager(execution_id=agent.id, provider=provider)
        coordinator = RecoveryCoordinator(manager)
        
        if await coordinator.can_recover():
            print(f"Resuming agent {agent.id} from checkpoint...")
            checkpoint = await manager.get_latest_checkpoint()
            await coordinator.recover_execution_state(agent)
            
            if checkpoint["metadata"].get("llm_response"):
                await StreamingPythonExecutor.resume_from_checkpoint(
                    agent, checkpoint
                )
    
    # Continue execution
    await playbooks.program.run_till_exit()

# Run
asyncio.run(run_with_auto_resume("blah.pb"))
```

### Custom Recovery Logic

```python
# Decide which checkpoint to resume from
checkpoints = await provider.list_checkpoints(agent.id)

# Resume from specific checkpoint (not latest)
checkpoint_id = checkpoints[-2]  # Second to last
checkpoint = await provider.load_checkpoint(checkpoint_id)

await coordinator.recover_execution_state(agent)
executor = await StreamingPythonExecutor.resume_from_checkpoint(
    agent, checkpoint
)
```

## Best Practices

### 1. Always Enable in Production

```toml
[durability]
enabled = true  # ← Always for production
```

### 2. Monitor Checkpoint Storage

```bash
# Check storage usage
du -sh .checkpoints/

# Adjust retention if needed
[durability]
keep_last_n = 20  # Keep more checkpoints
```

### 3. Test Resume Regularly

```bash
# During development, test resume:
playbooks run workflow.pb
# Hit Ctrl+C mid-execution
playbooks run workflow.pb --resume
# Verify it continues correctly
```

### 4. Clear Stale Checkpoints

```bash
# Before major changes, clear old checkpoints
rm -rf .checkpoints/

# Fresh start
playbooks run blah.pb
```

## Summary

### The Complete Flow

```bash
# 1. Enable durability
[durability]
enabled = true

# 2. Run playbook (checkpoints saved automatically)
playbooks run blah.pb

# 3. If interrupted, resume
playbooks run blah.pb --resume

# That's it! ✅
```

### What Gets Restored

- ✅ All variables (`$x`, `$data`, etc.)
- ✅ Call stack position
- ✅ Agent state
- ✅ Execution progress
- ✅ Namespace variables
- ✅ Execution continues from exact await point

### What Doesn't Require Manual Work

- ✅ Checkpoint creation (automatic)
- ✅ State serialization (automatic)
- ✅ Storage management (automatic)
- ✅ Cleanup (automatic)

## CLI Reference

```bash
playbooks run blah.pb [OPTIONS]

Options:
  --resume              Resume from last checkpoint
  -v, --verbose         Print session log
  --debug               Start debug server
  --stream=<bool>       Enable/disable streaming
  --snoop=<bool>        Display agent-to-agent messages
```

## Example Output

### Normal Execution

```
$ playbooks run blah.pb

Loading playbooks from: ['blah.pb']
Starting execution...
[Agent messages stream here]
Execution complete ✅
```

### With Resume

```
$ playbooks run blah.pb --resume

Loading playbooks from: ['blah.pb']
🔄 Found checkpoint for agent main_agent_1
   Checkpoint: main_agent_1_ckpt_7
   Last statement: data = await FetchData()...
✅ Resumed execution for agent main_agent_1
[Execution continues from checkpoint]
Execution complete ✅
```

## See Also

- `docs/guides/durable-execution.md` - Complete durability guide
- `CHECKPOINT_RESUME_DEMO.md` - Visual demonstration
- `examples/durable_execution_example.py` - Code examples

---

**You asked:** "Now how do I start `playbooks run blah.pb` again and get it to resume from the last checkpoint?"

**Answer:** `playbooks run blah.pb --resume` ✅

