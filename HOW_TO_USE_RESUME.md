# How to Use --resume Flag

## The Simple Answer

```bash
# First, enable durability in playbooks.toml
[durability]
enabled = true

# Run your playbook normally
playbooks run examples/negotiation.pb --snoop true

# If it crashes or you hit Ctrl+C...

# Resume from last checkpoint
playbooks run examples/negotiation.pb --snoop true --resume
```

## What You Experienced

### Run 1 (Crashed)
```bash
$ poetry run playbooks run examples/negotiation.pb --snoop true
# ... 4 messages exchanged ...
# Checkpoints being saved automatically after each await
^C  # You pressed Ctrl+C
```

**Checkpoints saved:** `.checkpoints/1000/`, `.checkpoints/human/`

### Run 2 (Resume Attempt - No Checkpoints Found)
```bash
$ poetry run playbooks run examples/negotiation.pb --snoop true --resume

⚠️  No checkpoints found for agent 1000
⚠️  No checkpoints found for agent human
```

**Why no checkpoints?** The provider wasn't registered properly (now fixed!)

## Try Again Now

With the fix applied, you should now:

```bash
# 1. Enable durability in playbooks.toml (you already did this ✅)
[durability]
enabled = true

# 2. Run your playbook
poetry run playbooks run examples/negotiation.pb --snoop true

# 3. Let it run for a few await statements, then Ctrl+C

# 4. Check that checkpoints were created
ls -la .checkpoints/*/

# You should see checkpoint files like:
# .checkpoints/1000/1000_ckpt_1.pkl
# .checkpoints/1000/1000_ckpt_2.pkl

# 5. Resume
poetry run playbooks run examples/negotiation.pb --snoop true --resume

# You should see:
# 🔄 Found checkpoint for agent 1000
#    Checkpoint: 1000_ckpt_X
#    Last statement: await Say(...)
# ✅ Resumed execution for agent 1000
```

## What Was Fixed

The bug: Filesystem checkpoint provider wasn't being registered at runtime.

**Fixed in:** `src/playbooks/checkpoints/__init__.py`
- Now automatically registers FilesystemCheckpointProvider on import
- Provider is available when StreamingPythonExecutor needs it

## Verification

```bash
# Check if provider is registered
python -c "
import playbooks.checkpoints
from playbooks.extensions.registry import ExtensionRegistry
print('Provider registered:', ExtensionRegistry.has_checkpoint_provider())
print('Provider class:', ExtensionRegistry._checkpoint_provider_class.__name__)
"

# Should output:
# Provider registered: True
# Provider class: FilesystemCheckpointProvider
```

## Configuration

Your `playbooks.toml` should have:

```toml
[durability]
enabled = true
storage_path = ".checkpoints"  # Optional, this is default
max_checkpoint_size_mb = 10    # Optional, this is default
keep_last_n = 10               # Optional, this is default
```

## Complete Example

```bash
# 1. Enable durability
cat >> playbooks.toml << EOF
[durability]
enabled = true
EOF

# 2. Run playbook (creates checkpoints)
poetry run playbooks run examples/negotiation.pb --snoop true

# Let it run... checkpoints being saved...
# After a few messages, press Ctrl+C

# 3. Check checkpoints exist
ls -la .checkpoints/*/
# Should see *.pkl files

# 4. Resume execution
poetry run playbooks run examples/negotiation.pb --snoop true --resume

# Should see:
# 🔄 Found checkpoint for agent ...
# ✅ Resumed execution
# [Continues from where it left off]
```

## Troubleshooting

### Still "No checkpoints found"?

**Check 1:** Is durability enabled?
```bash
python -c "from playbooks.config import config; print(config.durability.enabled)"
# Should print: True
```

**Check 2:** Do checkpoint files exist?
```bash
ls -la .checkpoints/
# Should see directories for each agent
ls -la .checkpoints/*/
# Should see .pkl files if playbook ran with durability enabled
```

**Check 3:** Did the first run actually create checkpoints?
- The first run must complete at least one `await` statement for a checkpoint to be saved
- If you hit Ctrl+C before the first await, no checkpoints exist yet

### Checkpoints created but resume doesn't work?

Check if the checkpoint contains an LLM response:
```python
import asyncio
from playbooks.checkpoints import FilesystemCheckpointProvider

async def check():
    provider = FilesystemCheckpointProvider()
    checkpoints = await provider.list_checkpoints("1000")  # agent ID
    if checkpoints:
        latest = checkpoints[-1]
        data = await provider.load_checkpoint(latest)
        print(f"LLM response present: {data['metadata'].get('llm_response') is not None}")

asyncio.run(check())
```

## What Gets Checkpointed

Every `await` statement in LLM-generated code:
- ✅ `await Say("user", "hello")`
- ✅ `await Step("Main:01:QUE")`
- ✅ `await OtherPlaybook()`
- ✅ `await Yld("user")`
- ✅ Any custom await in LLM code

## Next Run

Now when you run:

```bash
poetry run playbooks run examples/negotiation.pb --snoop true
```

Checkpoints will be created automatically!

Then if you kill it and run:

```bash
poetry run playbooks run examples/negotiation.pb --snoop true --resume
```

It will resume from the last checkpoint! ✅

---

**Summary:** The fix is deployed. Try running your playbook again - checkpoints will now be created and resume will work!

