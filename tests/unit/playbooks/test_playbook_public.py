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
    assert "square root" in pp[0].description
    assert agent0.playbooks["A"].public
    assert not agent0.playbooks["X"].public

    pp = agent1.public_playbooks
    assert len(pp) == 3
    assert pp[0].name == "GetLengthOfCountry"
    assert not pp[0].triggers
    assert pp[1].name == "GetCountryPopulation"
    assert not pp[1].triggers
    assert pp[2].name == "GetCountrySecret"
    assert len(pp[2].triggers.triggers) == 1
    assert "T1:CND" in str(pp[2].triggers.triggers[0])
    assert agent1.playbooks["GetLengthOfCountry"].public
    assert agent1.playbooks["GetCountryPopulation"].public
    assert agent1.playbooks["GetCountrySecret"].public
    assert not agent1.playbooks["LocalPB"].public
