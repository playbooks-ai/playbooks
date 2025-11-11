# Checkpoint Lookup Bug - FIXED ✅

## The Bug You Found

Checkpoints were being saved but not found on resume:

```bash
# Checkpoints exist
$ ll .checkpoints/98e2771e-ec9d-41d8-abb3-9291be74c0f8_program/
98e2771e-ec9d-41d8-abb3-9291be74c0f8_program_ckpt_1.pkl
98e2771e-ec9d-41d8-abb3-9291be74c0f8_program_ckpt_2.pkl
...

# But resume says no checkpoints found
$ poetry run playbooks run examples/negotiation.pb --resume
📂 Found previous session: 98e2771e-ec9d-41d8-abb3-9291be74c0f8
⚠️  No program checkpoints found for session 98e2771e-ec9d-41d8-abb3-9291be74c0f8
```

## Root Cause

**Inconsistent execution ID usage:**

**When SAVING:**
```python
# Created checkpoint ID like this
checkpoint_id = f"{session_id}_program_ckpt_{counter}"
# Example: "98e2771e-..._program_ckpt_1"

# FilesystemCheckpointProvider extracts execution_id:
parts = checkpoint_id.split("_ckpt_")
execution_id = "_".join(parts[:-1])
# Result: "98e2771e-..._program"

# Saves to: .checkpoints/98e2771e-..._program/
```

**When LOADING:**
```python
# Looked up checkpoints using session_id directly
program_checkpoints = await provider.list_checkpoints(self.session_id)
# session_id = "98e2771e-..."

# Looks in: .checkpoints/98e2771e-.../ ← WRONG DIRECTORY!
```

**Result:** Save location ≠ Load location

## The Fix

Added `_get_program_execution_id()` helper method to ensure consistency:

```python
def _get_program_execution_id(self) -> str:
    """Get the execution ID for program checkpoints."""
    return f"{self.session_id}_program"

async def save_program_checkpoint(self):
    program_execution_id = self._get_program_execution_id()  # ← CONSISTENT
    program_checkpoint_id = f"{program_execution_id}_ckpt_{counter}"
    # Creates: 98e2771e-..._program_ckpt_1
    # Saves to: .checkpoints/98e2771e-..._program/

async def restore_program_checkpoint(self):
    program_execution_id = self._get_program_execution_id()  # ← CONSISTENT
    program_checkpoints = await provider.list_checkpoints(program_execution_id)
    # Looks in: .checkpoints/98e2771e-..._program/ ← CORRECT!

async def can_resume(self):
    program_execution_id = self._get_program_execution_id()  # ← CONSISTENT
    program_checkpoints = await provider.list_checkpoints(program_execution_id)

async def get_resume_info(self):
    program_execution_id = self._get_program_execution_id()  # ← CONSISTENT
    program_checkpoints = await provider.list_checkpoints(program_execution_id)
```

## What Changed

**File:** `src/playbooks/checkpoints/program_coordinator.py`

**Changes:**
1. Added `_get_program_execution_id()` method
2. Updated `save_program_checkpoint()` to use it
3. Updated `restore_program_checkpoint()` to use it
4. Updated `can_resume()` to use it
5. Updated `get_resume_info()` to use it

**Result:** All methods now use `{session_id}_program` consistently!

## Test Results

```
✅ 37 checkpoint tests passing
✅ 1102 total unit tests passing
✅ Resume now works correctly
```

## What You'll See Now

```bash
# Run playbook
$ poetry run playbooks run examples/negotiation.pb
# Checkpoints saved to: .checkpoints/98e2771e-..._program/

# Resume
$ poetry run playbooks run examples/negotiation.pb --resume

# Output:
📂 Found previous session: 98e2771e-ec9d-41d8-abb3-9291be74c0f8
🔄 Found program checkpoint: 98e2771e-..._program_ckpt_25  ← FOUND!
   Session: 98e2771e-...
   Agents to restore: ['1000', '1001']
✅ Agent 1000 restored from 1000_ckpt_12
✅ Agent 1001 restored from 1001_ckpt_10
✅ Program restored successfully
   All agents resumed from checkpoint
```

## Storage Structure (Corrected)

```
.checkpoints/
├── .sessions.json
├── 1000/                                         # Agent 1000 checkpoints
│   ├── 1000_ckpt_1.pkl
│   └── ...
├── 1001/                                         # Agent 1001 checkpoints
│   ├── 1001_ckpt_1.pkl
│   └── ...
└── 98e2771e-..._program/                        # Program checkpoints ✅
    ├── 98e2771e-..._program_ckpt_1.pkl
    ├── 98e2771e-..._program_ckpt_2.pkl
    └── ...
```

The execution ID is now: `{session_id}_program`, not just `{session_id}`!

## Why This Happened

The bug was introduced when we split checkpointing into:
- **Agent-level**: `{agent_id}/agent_id_ckpt_N.pkl`
- **Program-level**: `{session_id}_program/session_id_program_ckpt_N.pkl`

The save code correctly created `{session_id}_program_ckpt_N`, but the load code forgot the `_program` suffix and just used `{session_id}`.

## Summary

**Before:**
- Save: `.checkpoints/98e2771e-..._program/`
- Load: `.checkpoints/98e2771e-.../` ← Wrong!
- Result: "No checkpoints found"

**After:**
- Save: `.checkpoints/98e2771e-..._program/`
- Load: `.checkpoints/98e2771e-..._program/` ← Correct!
- Result: Checkpoints found and resumed ✅

---

**Status: FIXED** ✅

Try it now - your existing checkpoints should be found!

