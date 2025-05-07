import pytest

from playbooks import Playbooks


@pytest.fixture
def md_file_name():
    return "multi-agent.md"


@pytest.fixture
def playbooks(md_path):
    return Playbooks([md_path])


def test_exports(playbooks):
    assert len(playbooks.program.agents) == 3

    agent0 = playbooks.program.agents[0]
    assert agent0.klass == "FirstAgent"
    assert len(agent0.exports) == 1
    assert agent0.exports[0]["name"] == "A"
    assert len(agent0.exports[0]["triggers"]) == 1
    assert agent0.exports[0]["triggers"][0] == "T1:CND When you need to compute square root"
    assert agent0.playbooks["A"].export
    assert not agent0.playbooks["X"].export

    agent1 = playbooks.program.agents[1]
    assert agent1.klass == "CountryInfo"
    assert len(agent1.exports) == 3
    assert agent1.exports[0]["name"] == "GetLengthOfCountry"
    assert "triggers" not in agent1.exports[0]
    assert agent1.exports[1]["name"] == "GetCountryPopulation"
    assert "triggers" not in agent1.exports[1]
    assert agent1.exports[2]["name"] == "GetCountrySecret"
    assert len(agent1.exports[2]["triggers"]) == 1
    assert (
        agent1.exports[2]["triggers"][0]
        == "T1:CND When you need to get a secret about a country"
    )
    assert agent1.playbooks["GetLengthOfCountry"].export
    assert agent1.playbooks["GetCountryPopulation"].export
    assert agent1.playbooks["GetCountrySecret"].export
    assert not agent1.playbooks["LocalPB"].export
