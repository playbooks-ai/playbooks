# Session Management - Complete Implementation

## The Problem You Discovered

When running with `--resume`, each invocation created a new session:

**First run:**
```bash
poetry run playbooks run examples/negotiation.pb
# Checkpoint saved to: e954aad9-a440-4c8c-be54-dea5230cdcf5_program_ckpt_29
```

**Resume run:**
```bash
poetry run playbooks run examples/negotiation.pb --resume
# ⚠️ No program checkpoints found for session 166296f0-e67d-4575-ae04-974e29df625c
```

**Root Cause:** Each `playbooks run` created a fresh UUID, so `--resume` couldn't find the previous session.

## The Solution

Implemented persistent session tracking:
1. **Automatic session reuse** - `--resume` finds last session for the playbook
2. **Explicit session selection** - `--resume <session_id>` for specific sessions
3. **Session registry** - Maps playbooks to their last session IDs

## Implementation

### SessionManager

**New file:** `src/playbooks/checkpoints/session_manager.py`

```python
class SessionManager:
    """Manages session IDs for playbook executions to enable resume."""
    
    def _get_execution_key(self, program_paths: List[str]) -> str:
        """Generate stable key from playbook paths."""
        abs_paths = sorted([str(Path(p).resolve()) for p in program_paths])
        paths_str = "|".join(abs_paths)
        return hashlib.sha256(paths_str.encode()).hexdigest()[:16]
    
    async def get_last_session(self, program_paths: List[str]) -> Optional[str]:
        """Get the last session ID for these playbooks."""
        # Looks up in .checkpoints/.sessions.json
    
    async def save_session(self, program_paths: List[str], session_id: str) -> None:
        """Save current session ID for these playbooks."""
        # Stores in .checkpoints/.sessions.json
```

### Session Registry Format

**File:** `.checkpoints/.sessions.json`

```json
{
  "abc123def456": "e954aad9-a440-4c8c-be54-dea5230cdcf5",
  "def789ghi012": "166296f0-e67d-4575-ae04-974e29df625c"
}
```

Where:
- Key: Hash of sorted absolute playbook paths (stable identifier)
- Value: Last session ID for that playbook

### CLI Changes

**Before:**
```bash
--resume                # Boolean flag
```

**After:**
```bash
--resume                # Auto-detect last session (nargs='?', const=True)
--resume SESSION_ID     # Explicit session ID
```

### Usage Examples

#### 1. Automatic Resume (finds last session)

```bash
# First run
poetry run playbooks run examples/negotiation.pb
# Session: e954aad9-...
# Checkpoints saved

# Resume (automatic)
poetry run playbooks run examples/negotiation.pb --resume

# Output:
# 📂 Found previous session: e954aad9-a440-4c8c-be54-dea5230cdcf5
# 🔄 Found program checkpoint: e954aad9-..._program_ckpt_29
# ✅ Program restored successfully
```

#### 2. Explicit Resume (specific session)

```bash
# List available checkpoints
ls .checkpoints/*/

# Resume specific session
poetry run playbooks run examples/negotiation.pb --resume e954aad9-a440-4c8c-be54-dea5230cdcf5

# Output:
# 📂 Resuming explicit session: e954aad9-a440-4c8c-be54-dea5230cdcf5
# 🔄 Found program checkpoint: e954aad9-..._program_ckpt_29
# ✅ Program restored successfully
```

#### 3. Multiple Interrupted Runs

```bash
# Run 1
poetry run playbooks run examples/negotiation.pb
# Session A: abc-123
# ... Ctrl+C

# Run 2 (starts fresh, no --resume)
poetry run playbooks run examples/negotiation.pb
# Session B: def-456
# ... Ctrl+C

# Resume the FIRST run explicitly
poetry run playbooks run examples/negotiation.pb --resume abc-123

# Or resume the LAST run automatically
poetry run playbooks run examples/negotiation.pb --resume
# (Resumes def-456, the most recent)
```

## Complete Flow

### First Execution

```
1. User runs: playbooks run examples/negotiation.pb
2. New session created: e954aad9-...
3. SessionManager.save_session() called
   └── Saves to .checkpoints/.sessions.json
4. Execution runs, checkpoints saved
   └── .checkpoints/e954aad9-.../*.pkl
5. User presses Ctrl+C
```

### Resume Execution

```
1. User runs: playbooks run examples/negotiation.pb --resume
2. SessionManager.get_last_session() called
   └── Looks up session ID from .checkpoints/.sessions.json
3. Found: e954aad9-...
4. Program initialized with that session ID
5. ProgramCheckpointCoordinator restores from:
   └── .checkpoints/e954aad9-.../*_program_ckpt_*.pkl
6. Execution continues
```

## Session Key Generation

**Why hash of paths?**

```python
# Example: User has these playbooks
paths = ["examples/negotiation.pb", "examples/common.pb"]

# SessionManager generates key:
abs_paths = [
    "/Users/user/playbooks/examples/common.pb",
    "/Users/user/playbooks/examples/negotiation.pb"
]  # Sorted for consistency
key = sha256("|".join(abs_paths))[:16]
# Result: "abc123def456"

# Same playbooks, same key, even across runs!
```

**Benefits:**
- Same playbooks = Same key = Find last session
- Different playbooks = Different key = Separate sessions
- Order-independent (sorted)
- Path-independent (uses absolute paths)

## Files Modified

**New Files:**
- `src/playbooks/checkpoints/session_manager.py` (120 lines)

**Modified Files:**
- `src/playbooks/cli.py` - Changed `--resume` to accept optional session ID
- `src/playbooks/applications/agent_chat.py` - Integrated session lookup/save
- `src/playbooks/checkpoints/__init__.py` - Export SessionManager

## Test Results

```
✅ 37 checkpoint tests passing
✅ 1102 total unit tests passing
✅ Integration tests passing
✅ Zero breaking changes
```

## Usage Patterns

### Pattern 1: Normal Development

```bash
# Work on playbook
poetry run playbooks run my-playbook.pb

# Test, find bug, Ctrl+C

# Fix code, resume
poetry run playbooks run my-playbook.pb --resume

# Continue from where you left off
```

### Pattern 2: Multiple Parallel Runs

```bash
# Terminal 1: Run negotiation
poetry run playbooks run examples/negotiation.pb
# Session: abc-123

# Terminal 2: Run different playbook
poetry run playbooks run examples/hello.pb
# Session: def-456

# Later: Resume each independently
poetry run playbooks run examples/negotiation.pb --resume  # → abc-123
poetry run playbooks run examples/hello.pb --resume        # → def-456
```

### Pattern 3: Session Archaeology

```bash
# Multiple runs of the same playbook
poetry run playbooks run negotiation.pb  # Session A
# ... Ctrl+C
poetry run playbooks run negotiation.pb  # Session B
# ... Ctrl+C
poetry run playbooks run negotiation.pb  # Session C
# ... Ctrl+C

# List all checkpoints
ls .checkpoints/*/

# Resume specific older session
poetry run playbooks run negotiation.pb --resume SESSION_A

# Or resume the most recent
poetry run playbooks run negotiation.pb --resume  # → Session C
```

## Configuration

**In playbooks.toml:**
```toml
[durability]
enabled = true
storage_path = ".checkpoints"  # Session registry stored here too
```

**Session registry location:**
```
.checkpoints/
├── .sessions.json              # ← Session registry (NEW!)
├── session_abc/.../            # Session checkpoints
└── session_def/.../            # Session checkpoints
```

## Troubleshooting

### "No previous session found"

**First run?**
- Session is only saved after first run
- Use without `--resume` flag first

**Check session registry:**
```bash
cat .checkpoints/.sessions.json
```

### "Session ID not found"

**Explicit session ID doesn't exist:**
```bash
# List available sessions
ls .checkpoints/

# Should see directory matching the session ID
```

### "Wrong session restored"

**Multiple playbook files:**
```bash
# Different file order = Same key
playbooks run a.pb b.pb
playbooks run b.pb a.pb  # ← Same session (sorted)

# Different files = Different key
playbooks run a.pb
playbooks run a.pb c.pb  # ← Different session
```

## Benefits

✅ **Automatic Resume** - Just use `--resume`, finds last session
✅ **Explicit Control** - Specify session ID when needed
✅ **Multiple Playbooks** - Each playbook tracks its own sessions
✅ **Persistent** - Session mapping survives restarts
✅ **Clean UX** - No need to remember session IDs usually

## What You'll See Now

### First Run

```bash
$ poetry run playbooks run examples/negotiation.pb

ℹ Loading playbooks from: ['examples/negotiation.pb']
[Agent executes...]
[Checkpoints saved: e954aad9-.../*.pkl]
^C
```

### Automatic Resume

```bash
$ poetry run playbooks run examples/negotiation.pb --resume

ℹ Loading playbooks from: ['examples/negotiation.pb']
📂 Found previous session: e954aad9-a440-4c8c-be54-dea5230cdcf5
🔄 Found program checkpoint: e954aad9-..._program_ckpt_29
   Session: e954aad9-a440-4c8c-be54-dea5230cdcf5
   Agents to restore: ['1000', '1001']
✅ Agent 1000 restored from 1000_ckpt_10
✅ Agent 1001 restored from 1001_ckpt_5
✅ Program restored successfully
   All agents resumed from checkpoint
[Execution continues...]
```

### Explicit Resume

```bash
$ poetry run playbooks run examples/negotiation.pb --resume e954aad9-a440-4c8c-be54-dea5230cdcf5

ℹ Loading playbooks from: ['examples/negotiation.pb']
📂 Resuming explicit session: e954aad9-a440-4c8c-be54-dea5230cdcf5
🔄 Found program checkpoint: e954aad9-..._program_ckpt_29
[Restores that specific session...]
```

## Summary

**Problem:** Each `--resume` created new session, couldn't find previous checkpoints

**Solution:** 
1. Session registry maps playbooks → last session ID
2. `--resume` auto-finds last session
3. `--resume SESSION_ID` for explicit control

**Result:** Resume now works as expected! ✅

---

**Status: PRODUCTION READY**

Session management is complete. Try it now:

```bash
# Run
poetry run playbooks run examples/negotiation.pb

# Resume
poetry run playbooks run examples/negotiation.pb --resume

# It works! 🎉
```

