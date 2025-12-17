import pytest

from playbooks import Playbooks


@pytest.fixture
def md_file_name():
    return "multi_agent_multi_begin.pb"


@pytest.fixture
def playbooks(md_path):
    return Playbooks([md_path])


@pytest.mark.asyncio
async def test_load_playbooks(playbooks):
    await playbooks.initialize()
    assert len(playbooks.program.agents) == 3  # including human agent


@pytest.mark.asyncio
async def test_begin(playbooks):
    await playbooks.initialize()
    await playbooks.program.run_till_exit()
    agent1_session_log = playbooks.program.agents[0].session_log.to_log_full()
    assert "A1P2() finished" in agent1_session_log
    assert "Say(user, A1P2" in agent1_session_log
    assert "Say(user, A1P3" in agent1_session_log

    agent2_session_log = playbooks.program.agents[1].session_log.to_log_full()
    assert "Say(user, A2P1" in agent2_session_log
    assert "Say(user, A2P2" in agent2_session_log
