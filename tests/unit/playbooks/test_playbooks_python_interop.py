import pytest

from playbooks import Playbooks
from playbooks.playbook import MarkdownPlaybook, PythonPlaybook


@pytest.fixture
def md_file_name():
    return "playbooks-python-interop.pb"


@pytest.fixture
def playbooks(md_path):
    return Playbooks([md_path])


def test_load_playbooks(playbooks):
    assert playbooks.program_content is not None
    assert playbooks.program_content != playbooks.compiled_program_content
    assert "BAXY" in playbooks.program_content

    assert playbooks.compiled_program_content is not None
    assert "BAXY" in playbooks.compiled_program_content


def test_load_program(playbooks):
    assert playbooks.program is not None
    assert playbooks.program.title == "Interop"


def test_load_agents(playbooks):
    assert playbooks.program is not None
    assert len(playbooks.program.agents) == 2  # One human agent
    assert playbooks.program.agents[0].klass == "Interop"

    agent = playbooks.program.agents[0]
    assert len(agent.playbooks) >= 10
    assert "X" in agent.playbooks
    assert isinstance(agent.playbooks["X"], MarkdownPlaybook)
    assert "A" in agent.playbooks
    assert isinstance(agent.playbooks["A"], PythonPlaybook)


@pytest.mark.asyncio
async def test_execute_playbook_A(playbooks):
    """Call a python playbook"""
    assert (
        await playbooks.program.agents[0].execute_playbook("A", kwargs={"num": 16}) == 4
    )


@pytest.mark.asyncio
async def test_execute_playbook_AB(playbooks):
    """Call a python playbook that calls another python playbook"""
    assert await playbooks.program.agents[0].execute_playbook("AB", args=[4]) == 4


@pytest.mark.asyncio
async def test_execute_playbook_X(playbooks):
    """Call a markdown playbook"""
    assert (
        await playbooks.program.agents[0].execute_playbook("X", kwargs={"num": 2}) == 4
    )


@pytest.mark.asyncio
async def test_execute_playbook_XY(playbooks):
    """Call a markdown playbook that calls another markdown playbook"""
    assert await playbooks.program.agents[0].execute_playbook("XY", args=[2]) == 2


@pytest.mark.asyncio
async def test_execute_playbook_CallX(playbooks):
    """Call a python playbook that calls a markdown playbook"""
    assert await playbooks.program.agents[0].execute_playbook("CallX", args=[2]) == 4


@pytest.mark.asyncio
async def test_execute_playbook_CallA(playbooks):
    """Call a markdown playbook that calls a python playbook"""
    assert await playbooks.program.agents[0].execute_playbook("CallA", args=[4]) == 2


@pytest.mark.asyncio
async def test_execute_playbook_Call_Complex(playbooks):
    """Test a complex call chain"""
    assert await playbooks.program.agents[0].execute_playbook("BAXY1", args=[8]) == 64
    assert await playbooks.program.agents[0].execute_playbook("BAXY2", args=[8]) == 64
