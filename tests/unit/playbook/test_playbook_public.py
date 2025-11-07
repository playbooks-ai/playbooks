import pytest

from playbooks import Playbooks


@pytest.fixture
def playbooks(test_data_dir):
    return Playbooks([test_data_dir / "multi-agent.pb"])


@pytest.mark.asyncio
async def test_public(playbooks):
    await playbooks.initialize()
    agent0, agent1, _ = playbooks.program.agents
    pp = agent0.public_playbooks
    assert len(pp) == 1
    assert pp[0].name == "A"
    assert len(pp[0].triggers.triggers) == 1
    assert "T1:CND" in str(pp[0].triggers.triggers[0])
    assert agent0.playbooks["A"].public
    assert not agent0.playbooks["X"].public

    pp = agent1.public_playbooks
    assert set([p.name for p in pp]) == set(
        ["GetLengthOfCountry", "GetCountryPopulation", "GetCountrySecret"]
    )

    assert not agent1.playbooks["GetLengthOfCountry"].triggers
    assert not agent1.playbooks["GetCountryPopulation"].triggers
    assert len(agent1.playbooks["GetCountrySecret"].triggers.triggers) == 1

    assert agent1.playbooks["GetLengthOfCountry"].public
    assert agent1.playbooks["GetCountryPopulation"].public
    assert agent1.playbooks["GetCountrySecret"].public
    assert not agent1.playbooks["LocalPB"].public
