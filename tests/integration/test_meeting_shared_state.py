import pytest

from playbooks import Playbooks
from playbooks.core.constants import EXECUTION_FINISHED


@pytest.mark.asyncio
async def test_meeting_shared_state(test_data_dir):
    playbooks = Playbooks([test_data_dir / "meeting-shared-state.pb"])
    await playbooks.initialize()
    await playbooks.program.run_till_exit()
    log = playbooks.program.agents_by_klass["Host"][0].session_log.to_log_full()
    # The participant guesses incorrectly, so "incorrect" should appear in the log
    assert "incorrect" in log.lower()
    assert EXECUTION_FINISHED in log
