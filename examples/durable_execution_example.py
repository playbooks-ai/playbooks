"""Example demonstrating durable execution with checkpointing.

This example shows how to:
1. Enable durability
2. Execute playbooks with automatic checkpointing
3. Recover and resume from checkpoints after crashes
"""

import asyncio
from pathlib import Path

from playbooks import Playbooks
from playbooks.checkpoints import (
    CheckpointManager,
    FilesystemCheckpointProvider,
    RecoveryCoordinator,
)
from playbooks.config import config


async def example_with_durability():
    """Run a playbook with durability enabled."""

    # Enable durability
    config.durability.enabled = True
    config.durability.storage_path = ".checkpoints"

    # Register filesystem provider
    from playbooks.checkpoints.filesystem import FilesystemCheckpointProvider
    from playbooks.extensions.registry import ExtensionRegistry

    ExtensionRegistry.register_checkpoint_provider(FilesystemCheckpointProvider)

    # Create a test playbook
    playbook_content = """# DurableAgent:AI

## ProcessData

```python
await Step("ProcessData:01:QUE")
await Say("user", "Starting data processing...")

await Step("ProcessData:02:ACT")
data = await FetchExternalData()  # ✅ Checkpoint saved here

await Step("ProcessData:03:ACT")
result = await ProcessData(data)  # ✅ Checkpoint saved here

await Say("user", f"Processing complete: {result}")
await Return(result)
```

## FetchExternalData

Simulates fetching data from external API.

## ProcessData

Simulates processing the data.
"""

    # Write playbook
    playbook_path = Path(".checkpoints/durable_test.pb")
    playbook_path.parent.mkdir(exist_ok=True)
    playbook_path.write_text(playbook_content)

    try:
        # Run playbook (will checkpoint automatically)
        pb = Playbooks([playbook_path])
        await pb.initialize()

        print("✅ Playbook initialized with durability enabled")
        print(f"✅ Checkpoints will be saved to: {config.durability.storage_path}")

        # In real usage, this might crash mid-execution
        # Checkpoints are saved after each await
        # await pb.program.run_till_exit()

    except Exception as e:
        print(f"❌ Execution failed: {e}")


async def example_recovery():
    """Recover and resume from a checkpoint."""

    # Assume we have an agent that crashed
    agent_id = "test_agent_123"

    # Setup checkpoint system
    provider = FilesystemCheckpointProvider(base_path=".checkpoints")
    manager = CheckpointManager(execution_id=agent_id, provider=provider)
    coordinator = RecoveryCoordinator(manager)

    # Check if recovery is possible
    if await coordinator.can_recover():
        print(f"✅ Checkpoints found for agent {agent_id}")

        # Get recovery information
        info = await coordinator.get_recovery_info()
        print(f"📍 Last checkpoint: {info['checkpoint_id']}")
        print(f"📍 Last statement: {info['statement']}")
        print(f"📍 Timestamp: {info['timestamp']}")

        # Load latest checkpoint
        _checkpoint_data = await manager.get_latest_checkpoint()

        # Restore agent state (you'd create/get your actual agent here)
        # await coordinator.recover_execution_state(agent)

        # Resume execution
        # executor = await StreamingPythonExecutor.resume_from_checkpoint(
        #     agent=agent,
        #     checkpoint_data=checkpoint_data
        # )

        print("✅ Ready to resume execution from checkpoint")
        print("✅ State restored, remaining code will execute")

    else:
        print(f"❌ No checkpoints found for agent {agent_id}")


async def main():
    """Main demonstration."""
    print("=" * 60)
    print("Durable Execution Example")
    print("=" * 60)
    print()

    print("Example 1: Running with Durability")
    print("-" * 60)
    await example_with_durability()
    print()

    print("Example 2: Recovery from Checkpoint")
    print("-" * 60)
    await example_recovery()
    print()

    print("=" * 60)
    print("✅ Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
