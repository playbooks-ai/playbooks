# Checkpoint Counter Reset Bug - FIXED ✅

## The Problem

**Your observation:**
```bash
# First run
Program checkpoint saved: ...ckpt_16 (agents: ['1000', '1001'])

# After resume
Found program checkpoint: ...ckpt_6
Program checkpoint saved: ...ckpt_1 (agents: ['1000'])  ← Reset to 1!
```

**What happened:**
1. First run created checkpoints 1-16
2. Resume loaded checkpoint 6 (or latest available)
3. **Checkpoint counter reset to 0**
4. Next checkpoint saved as ckpt_1, **overwriting** the old ckpt_1!
5. Continued saving ckpt_2, ckpt_3, etc., overwriting old checkpoints

## Root Cause

**Missing state restoration:**

```python
async def restore_program_checkpoint(self):
    # Restored agent state ✅
    # Restored program metadata ✅
    # Restored checkpoint counter ❌ ← MISSING!
    
    # So self.checkpoint_counter stayed at 0
    # Next save: ckpt_1 instead of ckpt_17
```

## The Fix

**Restore checkpoint counter from metadata:**

```python
async def restore_program_checkpoint(self):
    # ... load checkpoint ...
    
    # NEW: Resume checkpoint counter from where we left off
    if program_data and "metadata" in program_data:
        restored_counter = program_data["metadata"].get("checkpoint_counter", 0)
        self.checkpoint_counter = restored_counter
        logger.info(
            f"Resuming checkpoint counter from {restored_counter} "
            f"(latest checkpoint: {latest_program_ckpt})"
        )
```

## What This Fixes

**Before (Broken):**
```
First run:
  ckpt_1 → ckpt_2 → ... → ckpt_16 ✅
  (Ctrl+C)

Resume:
  Load ckpt_16 ✅
  Counter reset to 0 ❌
  Save ckpt_1 (overwrites!) ❌
  Save ckpt_2 (overwrites!) ❌
  ...
```

**After (Fixed):**
```
First run:
  ckpt_1 → ckpt_2 → ... → ckpt_16 ✅
  (Ctrl+C)

Resume:
  Load ckpt_16 ✅
  Counter restored to 16 ✅
  Save ckpt_17 ✅
  Save ckpt_18 ✅
  ...
```

## Why Only 1 Agent?

**Negotiation playbook execution flow:**
1. Agent 1000 (Seller) starts immediately
2. Checkpoint 1-6: Only agent 1000 exists
3. **Agent 1001 (Buyer) created dynamically** ("Create a Buyer agent")
4. Checkpoint 7+: Agents 1000 and 1001 exist
5. **Agent 1002 (Boss) created later** ("Create a Boss agent")
6. Checkpoint N+: All three agents exist

**When you resumed from checkpoint 6:**
- Agent 1001 hadn't been created yet at that point
- That's why it showed "1/1 agents restored"
- This is **correct behavior** - restoring the exact state at checkpoint 6

**If you had resumed from checkpoint 16:**
- Both agents 1000 and 1001 would have been restored
- Would show "2/2 agents restored"

## Complete Example

```bash
# First run (let it execute for a while)
$ playbooks run examples/negotiation.pb

# Checkpoints created:
ckpt_1: [1000]                    # Seller exists
ckpt_2: [1000]
...
ckpt_6: [1000]
ckpt_7: [1000, 1001]              # Buyer created!
ckpt_8: [1000, 1001]
...
ckpt_16: [1000, 1001]
^C  # Interrupt

# Resume
$ playbooks run examples/negotiation.pb --resume

# Without fix:
#   Restores ckpt_16 ✅
#   Counter = 0 ❌
#   Next: ckpt_1 (overwrites!)

# With fix:
#   Restores ckpt_16 ✅
#   Counter = 16 ✅
#   Next: ckpt_17 (continues!)
```

## Clean Up Old Checkpoints

If you want to start fresh:

```bash
# Remove old checkpoints
rm -rf .checkpoints/

# Or just for this session
rm -rf .checkpoints/bfadd904-a9a8-4fdf-ad67-5cadfd9e5788_program/
rm -rf .checkpoints/1000/
rm -rf .checkpoints/1001/

# Run fresh
playbooks run examples/negotiation.pb
```

## Summary

**Bug:** Checkpoint counter reset on resume, causing checkpoint overwriting

**Fix:** Restore `checkpoint_counter` from checkpoint metadata

**Result:** Checkpoints now continue incrementing correctly after resume

---

**Status: FIXED** ✅

Try running again - checkpoints will now continue from where they left off instead of overwriting!

