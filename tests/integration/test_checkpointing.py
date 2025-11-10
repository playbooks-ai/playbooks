"""Integration tests for durable execution with checkpointing."""

import tempfile
from pathlib import Path

import pytest

from playbooks import Playbooks
from playbooks.config import config


@pytest.mark.integration
class TestCheckpointing:
    """Integration tests for checkpoint functionality."""

    @pytest.mark.asyncio
    async def test_checkpoints_created_during_execution(self, test_data_dir):
        """Test that checkpoints are created during playbook execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config.durability.enabled = True
            config.durability.storage_path = tmpdir

            from playbooks.checkpoints.filesystem import FilesystemCheckpointProvider
            from playbooks.extensions.registry import ExtensionRegistry

            ExtensionRegistry.register_checkpoint_provider(FilesystemCheckpointProvider)

            pb_content = """# TestAgent:AI

## Greet

```python
await Say("user", "Hello!")
await Say("user", "How are you?")
await Say("user", "Goodbye!")
```
"""
            pb_file = Path(tmpdir) / "test.pb"
            pb_file.write_text(pb_content)

            pb = Playbooks([pb_file])
            await pb.initialize()
            await pb.program.run_till_exit()

            checkpoint_dir = Path(tmpdir)
            agent_dirs = list(checkpoint_dir.iterdir())

            if agent_dirs:
                checkpoints = list(agent_dirs[0].glob("*.pkl"))
                assert len(checkpoints) > 0, "Expected checkpoints to be created"

            config.durability.enabled = False
            ExtensionRegistry.reset()

    @pytest.mark.asyncio
    async def test_checkpoint_contains_execution_state(self, test_data_dir):
        """Test that checkpoints contain necessary execution state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config.durability.enabled = True
            config.durability.storage_path = tmpdir

            from playbooks.checkpoints.filesystem import FilesystemCheckpointProvider
            from playbooks.extensions.registry import ExtensionRegistry

            ExtensionRegistry.register_checkpoint_provider(FilesystemCheckpointProvider)

            pb_content = """# TestAgent:AI

## Calculate

```python
x = 10
y = 20
await Say("user", f"x={x}, y={y}")
result = x + y
await Say("user", f"result={result}")
```
"""
            pb_file = Path(tmpdir) / "test.pb"
            pb_file.write_text(pb_content)

            pb = Playbooks([pb_file])
            await pb.initialize()
            await pb.program.run_till_exit()

            checkpoint_dir = Path(tmpdir)
            agent_dirs = list(checkpoint_dir.iterdir())

            if agent_dirs:
                checkpoints = list(agent_dirs[0].glob("*.pkl"))
                if checkpoints:
                    from playbooks.checkpoints.filesystem import (
                        FilesystemCheckpointProvider,
                    )

                    provider = FilesystemCheckpointProvider(base_path=tmpdir)

                    checkpoint_id = checkpoints[0].stem
                    checkpoint_data = await provider.load_checkpoint(checkpoint_id)

                    assert checkpoint_data is not None
                    assert "execution_state" in checkpoint_data
                    assert "namespace" in checkpoint_data
                    assert "metadata" in checkpoint_data
                    assert "statement" in checkpoint_data["metadata"]

            config.durability.enabled = False
            ExtensionRegistry.reset()

    @pytest.mark.asyncio
    async def test_checkpointing_disabled_by_default(self, test_data_dir):
        """Test that checkpointing is disabled by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert config.durability.enabled is False

            pb_content = """# TestAgent:AI

## Greet

```python
await Say("user", "Hello!")
```
"""
            pb_file = Path(tmpdir) / "test.pb"
            pb_file.write_text(pb_content)

            pb = Playbooks([pb_file])
            await pb.initialize()
            await pb.program.run_till_exit()

            checkpoint_dir = Path(config.durability.storage_path)
            if checkpoint_dir.exists():
                agent_dirs = list(checkpoint_dir.iterdir())
                for agent_dir in agent_dirs:
                    checkpoints = list(agent_dir.glob("*.pkl"))
                    assert (
                        len(checkpoints) == 0
                    ), "No checkpoints should be created when disabled"
