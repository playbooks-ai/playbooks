from unittest.mock import MagicMock

import pytest

from playbooks import Playbooks
from playbooks.agents.local_ai_agent import LocalAIAgent
from playbooks.agents.mcp_agent import MCPAgent
from playbooks.constants import EOM, EXECUTION_FINISHED
from tests.unit.playbooks.test_mcp_end_to_end import InMemoryMCPTransport


@pytest.mark.asyncio
async def test_example_01(test_data_dir):
    playbooks = Playbooks([test_data_dir / "01-hello-playbooks.pb"])
    await playbooks.initialize()
    await playbooks.program.run_till_exit()
    log = playbooks.program.agents[0].state.session_log.to_log_full()
    assert 'Say("user"' in log
    assert EXECUTION_FINISHED in log


@pytest.mark.asyncio
async def test_example_02(test_data_dir):
    playbooks = Playbooks([test_data_dir / "02-personalized-greeting.pb"])
    await playbooks.initialize()
    ai_agent = playbooks.program.agents[0]

    # AI will ask name, so seed message from human with EOM
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, "John")
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, EOM)

    await playbooks.program.run_till_exit()
    log = playbooks.program.agents[0].state.session_log.to_log_full()
    print(log)
    assert "John" in log


@pytest.mark.asyncio
async def test_example_03(test_data_dir):
    playbooks = Playbooks([test_data_dir / "03-md-calls-python.pb"])
    await playbooks.initialize()
    ai_agent = playbooks.program.agents[0]

    # AI will ask for a number, so seed response from human
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, "10")
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, EOM)

    await playbooks.program.run_till_exit()
    log = playbooks.program.agents[0].state.session_log.to_log_full()
    assert "-5.44" in log


@pytest.mark.asyncio
async def test_example_04(test_data_dir):
    playbooks = Playbooks([test_data_dir / "04-md-python-md.pb"])
    await playbooks.initialize()
    await playbooks.program.run_till_exit()
    log = playbooks.program.agents[0].state.session_log.to_log_full()
    assert "generate_report_summary() finished" in log


@pytest.mark.asyncio
async def test_example_05(test_data_dir):
    playbooks = Playbooks([test_data_dir / "05-country-facts.pb"])
    await playbooks.initialize()
    # AI will ask for a country, so seed response from human
    await playbooks.program.agents_by_id["human"].SendMessage(
        playbooks.program.agents[0].id, "Bhutan"
    )

    await playbooks.program.run_till_exit()
    log = playbooks.program.agents[0].state.session_log.to_log_full()
    assert "India" in log
    assert "China" in log
    assert "Nepal" in log
    assert "Bangladesh" in log
    assert "Myanmar" in log


# @pytest.mark.asyncio
# async def test_example_08(test_data_dir):
#     playbooks = Playbooks([test_data_dir / "08-artifact.pb"])
#     await playbooks.program.run_till_exit()
#     log = playbooks.program.agents[0].state.session_log.to_log_full()
#     assert '`LoadArtifact("my_artifact")`' in log
#     assert '`LoadArtifact("another_artifact")`' in log

#     assert '`Say("Artifact[my_artifact]")`' in log
#     assert '`Say("This is a test artifact.")`' in log

#     assert '`Say("Artifact[another_artifact]")`' in log
#     assert '`Say("Secret message 54345.")`' in log

#     assert "SendMessage(human, Artifact[artifact1.txt])" in log
#     assert "SendMessage(human, This is artifact1.)" in log


# @pytest.mark.asyncio
# async def test_example_09(test_data_dir):
#     playbooks = Playbooks([test_data_dir / "09-create-playbook.pb"])
#     ai_agent = playbooks.program.agents[0]

#     # AI will ask task and clarification
#     await playbooks.program.agents_by_id["human"].SendMessage(
#         ai_agent.id, "add two numbers"
#     )
#     await playbooks.program.agents_by_id["human"].SendMessage(
#         ai_agent.id,
#         "integers only, as parameters $x and $y, return the result, no edge cases",
#     )

#     await playbooks.program.run_till_exit()
#     log = playbooks.program.agents[0].state.session_log.to_log_full()
#     assert "John" in log


@pytest.mark.asyncio
async def test_example_10(test_data_dir):
    playbooks = Playbooks([test_data_dir / "10-configs.pb"])
    await playbooks.initialize()
    await playbooks.program.create_agent("Accountant")
    await playbooks.program.create_agent("Paralegal")
    assert len(playbooks.program.agents) == 3

    accountant = playbooks.program.agents_by_klass["Accountant"][0]
    assert accountant.metadata["framework"] == "GAAP"
    assert accountant.metadata["author"] == "John Doe"
    assert accountant.metadata["specialization"][0] == "accounting"
    assert accountant.metadata["specialization"][1] == "tax"
    assert "metadata" not in accountant.description

    paralegal = playbooks.program.agents_by_klass["Paralegal"][0]
    assert paralegal.metadata["mcp"]["url"] == "http://lawoffice.com/Paralegal"
    assert paralegal.metadata["mcp"]["timeout"] == 10
    assert "metadata" not in paralegal.description


@pytest.mark.asyncio
async def test_example_11(test_data_dir, test_mcp_server_instance):
    playbooks = Playbooks([test_data_dir / "11-mcp-agent.pb"])
    await playbooks.initialize()
    mcp_agent = next(
        filter(lambda x: isinstance(x, MCPAgent), playbooks.program.agents)
    )
    markdown_agent = next(
        filter(lambda x: isinstance(x, LocalAIAgent), playbooks.program.agents)
    )

    mcp_agent.transport = InMemoryMCPTransport(test_mcp_server_instance)
    # await mcp_agent.initialize()

    await playbooks.program.run_till_exit()

    log = markdown_agent.state.session_log.to_log_full()

    # Check that the secret message appears in the log
    assert "Playbooks+MCP FTW!" in log


@pytest.mark.asyncio
async def test_example_12_timeout(test_data_dir):
    playbooks = Playbooks([test_data_dir / "12-menu-design-meeting.pb"])
    await playbooks.initialize()
    agent = playbooks.program.agents_by_klass["RestaurantConsultant"][0]
    human = playbooks.program.agents_by_id["human"]
    # mock such that `await self.meeting_manager._wait_for_required_attendees(meeting)` raises TimeoutError
    agent.meeting_manager._wait_for_required_attendees = MagicMock(
        side_effect=TimeoutError(
            "Timeout waiting for required attendees to join meeting. Missing: [HeadChef, MarketingSpecialist]"
        )
    )

    # AI will ask for a country, so seed response from human
    await human.SendMessage(agent.id, "indian restaurant menu redesign")
    await human.SendMessage(agent.id, EOM)
    await human.SendMessage(agent.id, "Add creative fusion Chaat items")
    await human.SendMessage(agent.id, EOM)
    await human.SendMessage(agent.id, "Let's try later")
    await human.SendMessage(agent.id, EOM)
    await human.SendMessage(agent.id, "Goodbye")
    await human.SendMessage(agent.id, EOM)
    await playbooks.program.run_till_exit()
    log = agent.state.session_log.to_log_full()

    assert "Meeting initialization failed" in log
    assert "apologize" in log


# @pytest.mark.asyncio
# async def test_example_two_player_game(test_data_dir):
#     playbooks = Playbooks([test_data_dir / "two-player-game.pb"])
#     await playbooks.initialize()
#     agent = playbooks.program.agents_by_klass["Host"][0]
#     human = playbooks.program.agents_by_id["human"]

#     await human.SendMessage(agent.id, "tic-tac-toe")
#     await human.SendMessage(agent.id, EOM)

#     await playbooks.program.run_till_exit()
#     log = agent.state.session_log.to_log_full()
#     print(log)
#     assert "GameRoom(" in log


@pytest.mark.asyncio
async def test_example_13_description_injection(test_data_dir):
    playbooks = Playbooks([test_data_dir / "13-description-injection.pb"])
    await playbooks.initialize()
    agent = playbooks.program.agents_by_klass["TestAgent"][0]

    await playbooks.program.run_till_exit()
    log = agent.state.session_log.to_log_full()
    print(log)
    assert "Greed" in log
