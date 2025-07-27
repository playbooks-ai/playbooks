import pytest

from playbooks import Playbooks
from playbooks.constants import EOM, HUMAN_AGENT_KLASS


@pytest.mark.asyncio
async def test_triggers(test_data_dir):
    playbooks = Playbooks([test_data_dir / "06-triggers.pb"])
    await playbooks.program.initialize()

    human = playbooks.program.agents_by_klass[HUMAN_AGENT_KLASS][0]
    ai = playbooks.program.agents_by_klass["ExampleProgram"][0]

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
    assert "Validation1(" in log
    assert " → 1234" in log

    # markdown playbook trigger on user providing an email
    assert "Validation2(" in log
    assert " → test@playbooks.com" in log

    # Trigger on variable set
    assert "TooBig() finished" in log

    # Make sure the program completed its task
    assert "LoadAccount" in log
    assert "8999" in log
