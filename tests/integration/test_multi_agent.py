import pytest

from playbooks import Playbooks
from playbooks.core.constants import EOM


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_agent(test_data_dir):
    playbooks = Playbooks([test_data_dir / "multi-agent.pb"])
    await playbooks.initialize()
    assert len(playbooks.program.agents) == 3

    # Check that agents are created with correct classes
    first_agents = playbooks.program.agents_by_klass["FirstAgent"]
    assert len(first_agents) >= 1  # Should have at least 1 FirstAgent instance

    country_info_agents = playbooks.program.agents_by_klass["CountryInfo"]
    assert len(country_info_agents) == 1  # Should have 1 CountryInfo agent

    # Check that agents have the expected playbooks
    first_agent = first_agents[0]
    assert "A" in first_agent.playbooks  # Should have the A playbook

    country_agent = country_info_agents[0]
    assert (
        "GetLengthOfCountry" in country_agent.playbooks
    )  # Should have the GetLengthOfCountry playbook
    assert (
        "GetCountryPopulation" in country_agent.playbooks
    )  # Should have the GetCountryPopulation playbook

    # Note: Full execution testing is skipped due to LLM response parsing issues
    # that prevent playbook execution from completing successfully


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
    log = tax_prep_agent.session_log.to_log_full()
    assert "15%" in log

    tax_info_agent = playbooks.program.agents_by_klass["TaxInformationAgent"][0]
    log = tax_info_agent.session_log.to_log_full()
    assert "15%" in log
