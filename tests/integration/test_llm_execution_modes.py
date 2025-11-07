import pytest

from playbooks import Playbooks
from playbooks.core.enums import LLMExecutionMode
from playbooks.execution.react import ReActLLMExecution


@pytest.fixture
def playbooks(test_data_dir):
    return Playbooks([test_data_dir / "07-execution-modes.pb"])


@pytest.mark.asyncio
async def test_execution_modes(playbooks):
    await playbooks.initialize()
    agent = playbooks.program.agents_by_klass["MathSolver"][0]

    assert agent.playbooks["Main"].execution_mode == LLMExecutionMode.PLAYBOOK
    assert agent.playbooks["Solver"].execution_mode == LLMExecutionMode.REACT
    assert agent.playbooks["Joke"].execution_mode == LLMExecutionMode.RAW


@pytest.mark.asyncio
async def test_react_playbook_steps(playbooks):
    await playbooks.initialize()
    agent = playbooks.program.agents_by_klass["MathSolver"][0]

    # Initially there are no steps
    assert agent.playbooks["Solver"].step_collection is None

    # When the playbook is executed, the steps are created
    execution = ReActLLMExecution(agent, agent.playbooks["Solver"])
    execution._add_react_steps()
    assert len(agent.playbooks["Solver"].step_collection) > 0


@pytest.mark.asyncio
async def test_raw_playbook_no_steps(playbooks):
    await playbooks.initialize()
    agent = playbooks.program.agents_by_klass["MathSolver"][0]

    assert agent.playbooks["Joke"].step_collection is None


@pytest.mark.asyncio
async def test_execution(playbooks):
    await playbooks.initialize()

    human = playbooks.program.agents_by_id["human"]
    agent = playbooks.program.agents_by_klass["MathSolver"][0]

    await human.SendMessage(agent.id, "sin(exp(3!))")

    await playbooks.program.run_till_exit()
    log = agent.state.session_log.to_log_full()
    assert "0.9" in log
    assert "Joke() → " in log
