import pytest

from playbooks import Playbooks
from playbooks.constants import EOM, EXECUTION_FINISHED


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_agent(test_data_dir):
    playbooks = Playbooks([test_data_dir / "multi-agent.pb"])
    await playbooks.initialize()
    assert len(playbooks.program.agents) == 3

    await playbooks.program.run_till_exit()

    first_agent = playbooks.program.agents[0]
    log = first_agent.state.session_log.to_log_full()
    assert "X() → " in log
    # assert "A(1024) → 32.0" in log

    country_info_agent = playbooks.program.agents[1]
    log = country_info_agent.state.session_log.to_log_full()
    # assert "GetCountrySecret(Canada) → " in log
    # assert "FirstAgent.A(num=5) → 2.23" in log
    # assert "GetCountryPopulation(India) → 2.23" in log
    assert "→ 32.0" in log
    assert EXECUTION_FINISHED in log


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_to_agent_interaction(test_data_dir):
    playbooks = Playbooks([test_data_dir / "two-agent.pb"])
    await playbooks.initialize()

    human = playbooks.program.agents_by_id["human"]
    tax_prep_agent = playbooks.program.agents_by_klass["TaxPreparationAgent"][0]
    await human.SendMessage(tax_prep_agent.id, "80000")
    await human.SendMessage(tax_prep_agent.id, EOM)

    await playbooks.program.run_till_exit()
    log = tax_prep_agent.state.session_log.to_log_full()
    assert "15%" in log

    tax_info_agent = playbooks.program.agents_by_klass["TaxInformationAgent"][0]
    log = tax_info_agent.state.session_log.to_log_full()
    assert "15%" in log
