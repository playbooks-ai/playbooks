import asyncio
import sys
from pathlib import Path

from playbooks import Playbooks
from playbooks.constants import EOM

sys.path.append(str(Path(__file__).parent.parent))


async def main():
    playbooks = Playbooks([Path(__file__).parent / "stock_analyst.pb"])
    await playbooks.initialize()
    ai_agent = playbooks.program.agents[0]

    # AI will ask name, so seed message from human with EOM
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, "AAPL")
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, EOM)

    await playbooks.program.run_till_exit()


if __name__ == "__main__":
    asyncio.run(main())
