import pytest

from playbooks import Playbooks


@pytest.fixture
def md_file_name():
    return "multi_agent_multi_begin.pb"


@pytest.fixture
def playbooks(md_path):
    return Playbooks([md_path])


def test_load_playbooks(playbooks):
    assert len(playbooks.program.agents) == 3  # including human agent


@pytest.mark.asyncio
async def test_begin(playbooks):
    await playbooks.program.run_till_exit()
    agent1_session_log = playbooks.program.agents[0].state.session_log.to_log_full()
    assert "python_a1p2() finished" in agent1_session_log
    assert "SendMessage(human, A1P2)" in agent1_session_log
    assert "SendMessage(human, A1P3)" in agent1_session_log

    agent2_session_log = playbooks.program.agents[1].state.session_log.to_log_full()
    assert "SendMessage(human, A2P1)" in agent2_session_log
    assert "SendMessage(human, A2P2)" in agent2_session_log
