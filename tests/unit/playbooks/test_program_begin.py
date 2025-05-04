import pytest

from playbooks import Playbooks


@pytest.fixture
def md_file_name():
    return "multi_agent_multi_begin.md"


@pytest.fixture
def playbooks(md_path):
    return Playbooks([md_path])


def test_load_playbooks(playbooks):
    assert len(playbooks.program.agents) == 3  # including human agent


@pytest.mark.asyncio
async def test_begin(playbooks):
    await playbooks.program.begin()
    agent1_session_log = str(playbooks.program.agents[0].state.session_log)
    assert "python_a1p2 finished" in agent1_session_log
    assert "A1P2 finished" in agent1_session_log
    assert "A1P3 finished" in agent1_session_log

    agent2_session_log = str(playbooks.program.agents[1].state.session_log)
    assert "A2P1 finished" in agent2_session_log
    assert "A2P2 finished" in agent2_session_log
