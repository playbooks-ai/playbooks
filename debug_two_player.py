#!/usr/bin/env python3
"""Debug script for two-player game issue."""

import asyncio
from pathlib import Path

from playbooks.main import Playbooks
from playbooks.constants import EOM


async def debug_two_player():
    """Debug the two-player game meeting issue step by step."""

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

    # Send the initial message
    print("\n=== Sending initial message ===")
    await human.SendMessage(host.id, "tic-tac-toe")
    await human.SendMessage(host.id, EOM)

    # Let it run for a bit and see what happens
    print("\n=== Starting execution ===")

    # Run for just a few seconds to see what happens
    try:
        await asyncio.wait_for(playbooks.program.run_till_exit(), timeout=10.0)
        print("Program completed normally")
    except asyncio.TimeoutError:
        print("Program timed out after 10 seconds")

        # Check what agents exist now
        print(f"\nFinal agents: {list(playbooks.program.agents_by_id.keys())}")
        print(
            f"Player agents: {[a.id for a in playbooks.program.agents_by_klass.get('Player', [])]}"
        )

        # Check if any agents have background processing running
        for agent_id, agent in playbooks.program.agents_by_id.items():
            if hasattr(agent, "_background_task"):
                running = agent._background_task and not agent._background_task.done()
                print(f"Agent {agent_id} background processing running: {running}")

        # Check the host's session log
        print("\nHost session log (last 10 lines):")
        log_lines = host.state.session_log.to_log_full().split("\n")
        for line in log_lines[-10:]:
            print(f"  {line}")


if __name__ == "__main__":
    asyncio.run(debug_two_player())
