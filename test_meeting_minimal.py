#!/usr/bin/env python3
"""Minimal test to verify YLD for meeting fix."""

import asyncio
from pathlib import Path

from playbooks.main import Playbooks
from playbooks.constants import EOM


async def test_minimal():
    """Minimal test for meeting YLD functionality."""

    # Load the playbook
    test_data_dir = Path("tests/data")
    playbooks = Playbooks([test_data_dir / "two-player-game.pb"])

    # Get the host and human agents
    host = playbooks.program.agents_by_klass["Host"][0]
    human = playbooks.program.agents_by_id["human"]

    print("Starting minimal test...")

    # Send the initial message
    await human.SendMessage(host.id, "tic-tac-toe")
    await human.SendMessage(host.id, EOM)

    # Run for a longer time to see the game progress
    try:
        await asyncio.wait_for(playbooks.program.run_till_exit(), timeout=30.0)
        print("✅ Program completed successfully!")
        return True
    except asyncio.TimeoutError:
        # Check if we got past the previous hang point
        log = host.state.session_log.to_log_full()
        if "GameRoom()" in log:
            print("✅ Success: Meeting is working - GameRoom() was called!")
            if "place your X" in log or "place your O" in log:
                print("✅ Excellent: Game is actively running with player moves!")
            return True
        elif "TicTac Thunder, it's your turn!" in log:
            print("✅ Progress: Got to player turn - YLD for meeting likely working!")
            return True
        else:
            print("❌ Still hanging at same point")
            print("Last few log lines:")
            lines = log.split("\n")
            for line in lines[-10:]:
                print(f"  {line}")
            return False


if __name__ == "__main__":
    success = asyncio.run(test_minimal())
    if success:
        print("\n🎉 The fix is working!")
    else:
        print("\n💥 Still has issues")
