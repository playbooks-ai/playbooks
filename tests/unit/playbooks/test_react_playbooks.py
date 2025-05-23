import pytest

from playbooks import Playbooks


@pytest.mark.asyncio
async def test_react_playbook_steps(test_data_dir):
    playbooks = Playbooks([test_data_dir / "07-react.pb"])
    react_playbook = playbooks.program.agents[0].playbooks["DeepResearch"]
    assert react_playbook.steps["type"] == "h3"
    assert react_playbook.steps["text"] == "Steps"
    assert len(react_playbook.steps["children"]) == 1
    assert len(react_playbook.step_collection) > 0
