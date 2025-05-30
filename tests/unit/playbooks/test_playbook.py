import pytest

from playbooks import Playbooks


@pytest.mark.asyncio
async def test_example_01(test_data_dir):
    playbooks = Playbooks([test_data_dir / "clover.pbc"])
    playbook = playbooks.program.agents[0].playbooks["Main"]
    assert playbook.step_collection

    steps = playbook.step_collection.steps
    assert len(steps) == 18
    assert steps["01"].source_line_number == 44
    assert steps["03"].source_line_number == 46
    assert steps["03.01"].source_line_number == 47
    assert steps["03.01.01"].source_line_number == 48
    assert steps["03.02"].source_line_number == 49
    assert steps["03.02.01"].source_line_number == 50
    assert steps["03.02.02"].source_line_number == 51
    assert steps["03.03"].source_line_number == 52

    assert len(steps["03"].children) == 6
    assert steps["03"].children[0] == steps["03.01"]
    assert steps["03"].children[1] == steps["03.02"]
    assert steps["03"].children[2] == steps["03.03"]
    assert steps["03"].children[3] == steps["03.04"]
    assert steps["03"].children[4] == steps["03.05"]
    assert steps["03"].children[5] == steps["03.06"]
