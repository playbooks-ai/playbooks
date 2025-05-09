import pytest

from playbooks import Playbooks


@pytest.fixture
def md_file_name():
    return "multi-agent.md"


@pytest.fixture
def playbooks(md_path):
    return Playbooks([md_path])


def test_public(playbooks):
    agent0, agent1, _ = playbooks.program.agents
    assert len(agent0.public) == 1
    assert agent0.public[0]["name"] == "A"
    assert len(agent0.public[0]["triggers"]) == 1
    assert "T1:CND" in agent0.public[0]["triggers"][0]
    assert agent0.playbooks["A"].public
    assert not agent0.playbooks["X"].public

    assert len(agent1.public) == 3
    assert agent1.public[0]["name"] == "GetLengthOfCountry"
    assert "triggers" not in agent1.public[0]
    assert agent1.public[1]["name"] == "GetCountryPopulation"
    assert "triggers" not in agent1.public[1]
    assert agent1.public[2]["name"] == "GetCountrySecret"
    assert len(agent1.public[2]["triggers"]) == 1
    assert "T1:CND" in agent1.public[2]["triggers"][0]
    assert agent1.playbooks["GetLengthOfCountry"].public
    assert agent1.playbooks["GetCountryPopulation"].public
    assert agent1.playbooks["GetCountrySecret"].public
    assert not agent1.playbooks["LocalPB"].public
