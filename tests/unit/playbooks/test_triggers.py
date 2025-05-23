import pytest

from playbooks import Playbooks
from playbooks.constants import EOM


@pytest.mark.asyncio
async def test_triggers(test_data_dir):
    playbooks = Playbooks([test_data_dir / "06-triggers.pb"])

    human = playbooks.program.agents_by_id["human"]
    ai = playbooks.program.agents[0]

    # AI will ask for PIN, first user will provide an invalid PIN
    await human.SendMessage(ai.id, "123")
    await human.SendMessage(ai.id, EOM)

    # Then user will provide a valid PIN
    await human.SendMessage(ai.id, "1234")
    await human.SendMessage(ai.id, EOM)

    # Then user will provide an invalid email
    await human.SendMessage(ai.id, "test@blah")
    await human.SendMessage(ai.id, EOM)

    # Then user will provide a valid email
    await human.SendMessage(ai.id, "test@playbooks.com")
    await human.SendMessage(ai.id, EOM)

    await playbooks.program.run_till_exit()
    log = ai.state.session_log.to_log_full()

    # python playbook trigger on user providing a PIN
    assert "Validation1()" in log

    # markdown playbook trigger on user providing an email
    assert "Validation2()" in log

    # Trigger on variable set
    assert "TooBig()" in log

    # Trigger on after calling a playbook
    assert "PB1()" in log

    # Make sure the program completed its task
    assert "LoadAccount()" in log
    assert "$8999" in log
