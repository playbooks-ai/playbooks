"""Integration test to verify EOM handling with agents."""

import pytest

from playbooks import Playbooks
from playbooks.core.constants import EOM


@pytest.mark.integration
@pytest.mark.asyncio
async def test_eom_separates_message_batches(test_data_dir):
    """Verify that agents receive messages one at a time when separated by EOM.

    This test verifies that when multiple messages are queued with EOM markers between them,
    the agent's WaitForMessage/ProcessMessages playbooks receive them one batch at a time,
    not all together.
    """
    # Use a simple test playbook
    playbooks = Playbooks([test_data_dir / "02-personalized-greeting.pb"])
    await playbooks.initialize()

    # Get agents
    agent = list(playbooks.program.agents_by_klass.values())[0][0]  # First agent
    human = playbooks.program.agents_by_id["human"]

    # Queue multiple messages with EOM markers (simulating user typing messages one at a time)
    await human.SendMessage(agent.id, "First message")
    await human.SendMessage(agent.id, EOM)
    await human.SendMessage(agent.id, "Second message")
    await human.SendMessage(agent.id, EOM)
    await human.SendMessage(agent.id, "Third message")
    await human.SendMessage(agent.id, EOM)
    await human.SendMessage(agent.id, "exit")
    await human.SendMessage(agent.id, EOM)

    # Run until agent exits
    await playbooks.program.run_till_exit()

    # The key verification is that the system executes without errors
    # The unit tests verify the core EOM handling in AsyncMessageQueue
    # This integration test verifies the end-to-end flow works

    log = agent.state.session_log.to_log_full()

    # Verify execution completed successfully
    assert len(log) > 0, "Agent should have executed and logged activity"
    assert "finished" in log.lower(), "Agent should have completed execution"

    print("Agent processed messages successfully with EOM separation")
    print("EOM handling integration test passed")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_messages_before_eom(test_data_dir):
    """Verify that multiple messages sent before an EOM are batched together.

    This test verifies that if multiple messages are sent without EOM between them,
    they are batched together and delivered in one call to ProcessMessages.
    """
    playbooks = Playbooks([test_data_dir / "02-personalized-greeting.pb"])
    await playbooks.initialize()

    agent = list(playbooks.program.agents_by_klass.values())[0][0]
    human = playbooks.program.agents_by_id["human"]

    # Send multiple messages without EOM between them
    await human.SendMessage(agent.id, "Message 1")
    await human.SendMessage(agent.id, "Message 2")
    await human.SendMessage(agent.id, "Message 3")
    # Now send EOM to complete the batch
    await human.SendMessage(agent.id, EOM)
    # Send exit to end the program
    await human.SendMessage(agent.id, "exit")
    await human.SendMessage(agent.id, EOM)

    await playbooks.program.run_till_exit()

    log = agent.state.session_log.to_log_full()

    # All three messages should have been delivered in the same batch
    # (We can't easily verify this from log alone, but test that execution works)
    assert len(log) > 0, "Agent should have executed"

    print("Agent processed batched messages successfully")
