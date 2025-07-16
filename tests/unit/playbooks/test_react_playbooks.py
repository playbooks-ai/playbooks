import pytest

from playbooks import Playbooks


@pytest.mark.asyncio
async def test_react_playbook_steps(test_data_dir):
    playbooks = Playbooks([test_data_dir / "07-react.pb"])
    await playbooks.initialize()
    react_playbook = playbooks.program.agents_by_klass["MathSolver"][0]
    react_playbook = react_playbook.playbooks["Solver"]
    assert len(react_playbook.steps) > 0


@pytest.mark.asyncio
async def test_react_playbook_execution(test_data_dir):
    playbooks = Playbooks([test_data_dir / "07-react.pb"])
    await playbooks.initialize()

    human = playbooks.program.agents_by_id["human"]
    agent = playbooks.program.agents_by_klass["MathSolver"][0]

    await human.SendMessage(agent.id, "sin(exp(3!))")

    await playbooks.program.run_till_exit()
    log = agent.state.session_log.to_log_full()
    assert "0.96" in log
