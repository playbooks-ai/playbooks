#!/usr/bin/env python3
"""Debug script to check meeting invitation delivery."""

import asyncio
from pathlib import Path

from playbooks.main import Playbooks
from playbooks.constants import EOM


async def debug_meeting_invitations():
    """Debug meeting invitation delivery step by step."""

    # Load the playbook
    test_data_dir = Path("tests/data")
    playbooks = Playbooks([test_data_dir / "two-player-game.pb"])

    print("=== Initial State ===")
    print(f"Available agent classes: {list(playbooks.program.agents_by_klass.keys())}")
    print(f"Initial agents: {list(playbooks.program.agents_by_id.keys())}")

    # Get the host and human agents
    host = playbooks.program.agents_by_klass["Host"][0]
    human = playbooks.program.agents_by_id["human"]

    print(f"Host agent ID: {host.id}")
    print(f"Human agent ID: {human.id}")

    # Start the program
    await human.SendMessage(host.id, "tic-tac-toe")
    await human.SendMessage(host.id, EOM)

    # Let it run for just a few seconds to create agents
    print("\n=== Running to create agents ===")
    try:
        await asyncio.wait_for(playbooks.program.run_till_exit(), timeout=5.0)
        print("Program completed normally")
    except asyncio.TimeoutError:
        print("Program timed out after 5 seconds")

    print(f"\nFinal agents: {list(playbooks.program.agents_by_id.keys())}")

    # Check if we have new agents
    new_agents = []
    for agent_id, agent in playbooks.program.agents_by_id.items():
        if agent_id not in ["1000", "1001", "human"]:
            new_agents.append(agent)
            print(f"New agent: {agent_id} ({agent.klass})")
            print(f"  - Has inbox: {hasattr(agent, 'inbox')}")
            if hasattr(agent, "inbox"):
                print(f"  - Inbox message count: {agent.inbox.messages.qsize()}")
                print(f"  - Waiting mode: {agent.inbox.waiting_state.mode}")
            print(
                f"  - Has playbooks: {len(agent.playbooks) if hasattr(agent, 'playbooks') else 'N/A'}"
            )
            if hasattr(agent, "playbooks"):
                meeting_playbooks = [
                    name
                    for name, pb in agent.playbooks.items()
                    if getattr(pb, "meeting", False)
                ]
                print(f"  - Meeting playbooks: {meeting_playbooks}")

    # Now manually test meeting invitation
    if len(new_agents) >= 2:
        print("\n=== Testing Manual Meeting Invitation ===")
        agent1 = new_agents[0]
        agent2 = new_agents[1]

        print(
            f"Testing invitation from Host {host.id} to agents {agent1.id} and {agent2.id}"
        )

        # Send meeting invitation manually
        from playbooks.message_system import AgentMessage

        invitation_msg = AgentMessage(
            sender_id=host.id,
            content="Test meeting topic",
            message_type="meeting_invite",
            meeting_id="TEST_100",
        )

        print(f"Sending invitation to {agent1.id}")
        agent1.inbox.add_message(invitation_msg)
        print(
            f"Agent1 inbox after invitation: {agent1.inbox.messages.qsize()} messages"
        )

        invitation_msg2 = AgentMessage(
            sender_id=host.id,
            content="Test meeting topic",
            message_type="meeting_invite",
            meeting_id="TEST_100",
        )

        print(f"Sending invitation to {agent2.id}")
        agent2.inbox.add_message(invitation_msg2)
        print(
            f"Agent2 inbox after invitation: {agent2.inbox.messages.qsize()} messages"
        )

        # Check if the message delivery processor would deliver these
        print("\n=== Checking Delivery Conditions ===")
        print(
            f"Agent1 delivery condition met: {agent1.inbox.check_delivery_condition()}"
        )
        print(
            f"Agent2 delivery condition met: {agent2.inbox.check_delivery_condition()}"
        )

        # Wait a moment for message delivery
        await asyncio.sleep(1.0)

        print("\nAfter 1 second:")
        print(f"Agent1 inbox: {agent1.inbox.messages.qsize()} messages")
        print(f"Agent2 inbox: {agent2.inbox.messages.qsize()} messages")

        # Check their session logs for any invitation processing
        for i, agent in enumerate([agent1, agent2], 1):
            if hasattr(agent, "state") and hasattr(agent.state, "session_log"):
                log = agent.state.session_log.to_log_full()
                print(f"\nAgent{i} session log:")
                if log.strip():
                    for line in log.split("\n")[-5:]:  # Last 5 lines
                        print(f"  {line}")
                else:
                    print("  (empty)")


if __name__ == "__main__":
    asyncio.run(debug_meeting_invitations())
