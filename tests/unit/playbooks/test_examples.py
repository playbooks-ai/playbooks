import pytest

from playbooks import Playbooks


@pytest.mark.asyncio
async def test_example_01(test_data_dir):
    playbooks = Playbooks([test_data_dir / "01-hello-playbooks.pb"])
    await playbooks.program.run_till_exit()
    log = playbooks.program.agents[0].state.session_log.to_log_full()
    assert "SendMessage(human" in log


@pytest.mark.asyncio
async def test_example_02(test_data_dir):
    playbooks = Playbooks([test_data_dir / "02-personalized-greeting.pb"])
    ai_agent = playbooks.program.agents[0]

    # AI will ask name, so seed message from human
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, "John")

    await playbooks.program.run_till_exit()
    log = playbooks.program.agents[0].state.session_log.to_log_full()
    assert "John" in log


@pytest.mark.asyncio
async def test_example_03(test_data_dir):
    playbooks = Playbooks([test_data_dir / "03-md-calls-python.pb"])
    ai_agent = playbooks.program.agents[0]

    # AI will ask for a number, so seed response from human
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, "10")

    await playbooks.program.run_till_exit()
    log = playbooks.program.agents[0].state.session_log.to_log_full()
    assert "-5.44" in log


@pytest.mark.asyncio
async def test_example_04(test_data_dir):
    playbooks = Playbooks([test_data_dir / "04-md-python-md.pb"])
    await playbooks.program.run_till_exit()
    log = playbooks.program.agents[0].state.session_log.to_log_full()
    assert "generate_report_summary()" in log
    assert "FormatSummary()" in log
    assert "SendMessage(human" in log


@pytest.mark.asyncio
async def test_example_05(test_data_dir):
    playbooks = Playbooks([test_data_dir / "05-country-facts.pb"])

    # AI will ask for a country, so seed response from human
    await playbooks.program.agents_by_id["human"].SendMessage(
        playbooks.program.agents[0].id, "Bhutan"
    )

    await playbooks.program.run_till_exit()
    log = playbooks.program.agents[0].state.session_log.to_log_full()
    assert log.count("GetCountryFact() returned") == 5


@pytest.mark.asyncio
async def test_example_08(test_data_dir):
    playbooks = Playbooks([test_data_dir / "08-artifact.pb"])
    await playbooks.program.run_till_exit()
    log = playbooks.program.agents[0].state.session_log.to_log_full()
    assert '`LoadArtifact("my_artifact")`' in log
    assert '`LoadArtifact("another_artifact")`' in log

    assert '`Say("Artifact[my_artifact]")`' in log
    assert '`Say("This is a test artifact.")`' in log

    assert '`Say("Artifact[another_artifact]")`' in log
    assert '`Say("Secret message 54345.")`' in log

    assert "SendMessage(human, Artifact[artifact1.txt])" in log
    assert "SendMessage(human, This is artifact1.)" in log


@pytest.mark.asyncio
async def test_example_09(test_data_dir):
    playbooks = Playbooks([test_data_dir / "09-create-playbook.pb"])
    ai_agent = playbooks.program.agents[0]

    # AI will ask task and clarification
    await playbooks.program.agents_by_id["human"].SendMessage(
        ai_agent.id, "add two numbers"
    )
    await playbooks.program.agents_by_id["human"].SendMessage(
        ai_agent.id,
        "integers only, as parameters $x and $y, return the result, no edge cases",
    )

    await playbooks.program.run_till_exit()
    log = playbooks.program.agents[0].state.session_log.to_log_full()
    assert "John" in log
