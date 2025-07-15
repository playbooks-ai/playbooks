import pytest

from playbooks import Playbooks


@pytest.mark.asyncio
async def test_multi_agent(test_data_dir):
    playbooks = Playbooks([test_data_dir / "multi-agent.pb"])
    await playbooks.initialize()
    assert len(playbooks.program.agents) == 3

    await playbooks.program.run_till_exit()

    first_agent = playbooks.program.agents[0]
    log = first_agent.state.session_log.to_log_full()
    assert "X() → 10 2.23" in log
    # assert "A(1024) → 32.0" in log

    country_info_agent = playbooks.program.agents[1]
    log = country_info_agent.state.session_log.to_log_full()
    # assert "GetCountrySecret(Canada) → " in log
    # assert "FirstAgent.A(num=5) → 2.23" in log
    # assert "GetCountryPopulation(India) → 2.23" in log
    assert "→ 32.0" in log
    assert "yld for exit" in log
