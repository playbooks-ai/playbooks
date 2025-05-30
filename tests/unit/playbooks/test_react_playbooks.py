import pytest

from playbooks import Playbooks


@pytest.mark.asyncio
async def test_react_playbook_steps(test_data_dir):
    playbooks = Playbooks([test_data_dir / "07-react.pb"])
    react_playbook = playbooks.program.agents[0].playbooks["DeepResearch"]
    assert len(react_playbook.steps) > 0
