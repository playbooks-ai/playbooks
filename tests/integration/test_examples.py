import re
import subprocess
from pathlib import Path

import pytest

from playbooks import Playbooks
from playbooks.agents.local_ai_agent import LocalAIAgent
from playbooks.agents.mcp_agent import MCPAgent
from playbooks.core.constants import EOM, EXECUTION_FINISHED
from tests.conftest import extract_messages_from_cli_output
from tests.integration.test_mcp_end_to_end import InMemoryMCPTransport


@pytest.mark.asyncio
async def test_example_01(test_data_dir):
    playbooks = Playbooks([test_data_dir / "01-hello-playbooks.pb"])
    await playbooks.initialize()
    await playbooks.program.run_till_exit()
    log = playbooks.program.agents[0].session_log.to_log_full()
    assert "HelloWorldDemo()" in log
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
    log = playbooks.program.agents[0].session_log.to_log_full()
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
    log = playbooks.program.agents[0].session_log.to_log_full()
    assert "-5.44" in log


@pytest.mark.asyncio
async def test_example_04(test_data_dir):
    playbooks = Playbooks([test_data_dir / "04-md-python-md.pb"])
    await playbooks.initialize()
    await playbooks.program.run_till_exit()
    log = playbooks.program.agents[0].session_log.to_log_full()
    assert "generate_report_summary()" in log


@pytest.mark.asyncio
async def test_example_05(test_data_dir):
    playbooks = Playbooks([test_data_dir / "05-country-facts.pb"])
    await playbooks.initialize()
    # AI will ask for a country, so seed response from human
    await playbooks.program.agents_by_id["human"].SendMessage(
        playbooks.program.agents[0].id, "Bhutan"
    )

    await playbooks.program.run_till_exit()
    log = playbooks.program.agents[0].session_log.to_log_full()
    assert "India" in log
    assert "Nepal" in log


# @pytest.mark.asyncio
# async def test_example_08(test_data_dir):
#     playbooks = Playbooks([test_data_dir / "08-artifact.pb"])
#     await playbooks.program.run_till_exit()
#     log = playbooks.program.agents[0].session_log.to_log_full()
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
#     log = playbooks.program.agents[0].session_log.to_log_full()
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
    await mcp_agent.initialize()

    await playbooks.program.run_till_exit()

    log = markdown_agent.session_log.to_log_full()

    # Check that the secret message appears in the log
    assert "Playbooks+MCP FTW!" in log


# @pytest.mark.integration
# @pytest.mark.asyncio
# async def test_example_12_timeout(test_data_dir):
#     playbooks = Playbooks([test_data_dir / "12-menu-design-meeting.pb"])
#     await playbooks.initialize()
#     agent = playbooks.program.agents_by_klass["RestaurantConsultant"][0]
#     human = playbooks.program.agents_by_id["human"]

#     # Mock _wait_for_required_attendees to raise TimeoutError
#     # Apply mock before any agent execution starts
#     async def mock_wait_for_attendees(meeting, timeout_seconds=30):
#         raise TimeoutError(
#             "Timeout waiting for required attendees to join meeting. Missing: [HeadChef, MarketingSpecialist]"
#         )

#     # Ensure mock is applied before agent begins execution
#     agent.meeting_manager._wait_for_required_attendees = mock_wait_for_attendees

#     # AI will ask for reasons and constraints, so seed responses from human
#     await human.SendMessage(agent.id, "indian restaurant menu redesign")
#     await human.SendMessage(agent.id, EOM)
#     # Agent will ask for reasons and constraints
#     await human.SendMessage(
#         agent.id,
#         "I want to add creative fusion Chaat items to attract younger customers. Budget is $10k, timeline is 2 months.",
#     )
#     await human.SendMessage(agent.id, EOM)
#     await playbooks.program.run_till_exit()
#     log = agent.session_log.to_log_full()

#     assert "Meeting initialization failed" in log
#     assert "Timeout" in log


@pytest.mark.integration
@pytest.mark.asyncio
async def test_example_two_player_game(test_data_dir):
    playbooks = Playbooks([test_data_dir / "two-player-game.pb"])
    await playbooks.initialize()
    agent = playbooks.program.agents_by_klass["Host"][0]
    human = playbooks.program.agents_by_id["human"]

    await human.SendMessage(
        agent.id,
        "Guess the number - first player selects a secret number between 1 and 5. Second player has up to 2 guesses. For each guess, first player responds with my number is smaller, larger or found",
    )
    await human.SendMessage(agent.id, EOM)

    await playbooks.program.run_till_exit()

    # Check for agent errors after test execution
    if playbooks.has_agent_errors():
        agent_errors = playbooks.get_agent_errors()
        error_details = "\n".join(
            [
                f"Agent {error['agent_name']}: {error['error_type']} - {error['error']}"
                for error in agent_errors
            ]
        )
        pytest.fail(f"Agent errors detected during test execution:\n{error_details}")
    log = agent.session_log.to_log_full()
    print(log)
    assert "GameRoom(" in log


@pytest.mark.integration
@pytest.mark.asyncio
async def test_example_13_description_injection(test_data_dir):
    playbooks = Playbooks([test_data_dir / "13-description-injection.pb"])
    await playbooks.initialize()
    agent = playbooks.program.agents_by_klass["TestAgent"][0]

    await playbooks.program.run_till_exit()
    log = agent.session_log.to_log_full()
    print(log)
    assert "Greed" in log
    # Variable is stored as jk (without $ prefix) in new system
    assert (
        playbooks.program.agents_by_klass["TestAgent"][0].state.jk
        == "Why was the computer cold? It left its Windows open."
    )


# @pytest.skip(reason="Not a test, debugging aid only")
# @pytest.mark.asyncio
# async def test_example_deep_file_researcher(test_examples_dir):
#     # Run the MCP server before running the test
#     playbooks = Playbooks(
#         [test_examples_dir / "deep_file_researcher" / "deep_file_researcher.pb"]
#     )
#     await playbooks.initialize()
#     agent = playbooks.program.agents_by_klass["DeepFileResearcher"][0]
#     human = playbooks.program.agents_by_id["human"]

#     await human.SendMessage(agent.id, "/Users/amolk/work/workspace/playbooks-docs/docs")
#     await human.SendMessage(agent.id, EOM)

#     await human.SendMessage(agent.id, "How does Playbooks manage LLM context?")
#     await human.SendMessage(agent.id, EOM)

#     await human.SendMessage(agent.id, "goodbye")
#     await human.SendMessage(agent.id, EOM)

#     await playbooks.program.run_till_exit()
#     log = agent.session_log.to_log_full()
#     print(log)
#     assert "FileSystemAgent.extract_table_of_contents" in log
#     assert "FileSystemAgent.read_file" in log
#     assert "Execution finished" in log


@pytest.mark.asyncio
async def test_example_14_python_only(test_data_dir, monkeypatch):
    """Test that python-only playbook executes without any LLM calls."""
    # Track LLM calls
    llm_call_count = 0

    def mock_get_completion(*args, **kwargs):
        nonlocal llm_call_count
        llm_call_count += 1
        pytest.fail(f"LLM call made when none expected. Call count: {llm_call_count}")

    # Import and patch the LLM helper
    from playbooks.utils import llm_helper

    monkeypatch.setattr(llm_helper, "get_completion", mock_get_completion)

    playbooks = Playbooks([test_data_dir / "14-python-only.pb"])
    await playbooks.initialize()
    ai_agent = playbooks.program.agents[0]

    # Send response to WaitForMessage
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, "Alice")
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, EOM)

    await playbooks.program.run_till_exit()

    log = ai_agent.session_log.to_log_full()

    print("=== Session Log ===")
    print(log)
    print("===================")

    # Verify expected output
    assert "What's your name?" in log
    assert "Received messages" in log
    assert "Alice" in log
    assert "Secret code: OhSoSecret!" in log
    assert "GetSecret()" in log
    assert "EndProgram()" in log  # Verify Exit was called

    # Verify no LLM calls were made
    assert llm_call_count == 0, f"Expected 0 LLM calls, but got {llm_call_count}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_example_storyteller(test_examples_dir):
    # Run the MCP server before running the test
    playbooks = Playbooks([test_examples_dir / "storyteller.pb"])
    await playbooks.initialize()
    storyteller = playbooks.program.agents_by_klass["StoryTeller"][0]
    human = playbooks.program.agents_by_id["human"]

    await human.SendMessage(storyteller.id, "cotton candy")
    await human.SendMessage(storyteller.id, EOM)

    await playbooks.program.run_till_exit()
    log = storyteller.session_log.to_log_full()
    assert "Main()" in log
    assert "Execution finished" in log

    character_creator = playbooks.program.agents_by_klass["CharacterCreator"][0]
    log = character_creator.session_log.to_log_full()
    assert "CreateNewCharacter() →" in log


@pytest.mark.integration
def test_streaming_vs_nonstreaming_consistency(test_data_dir):
    """Test that streaming and non-streaming modes produce the same messages.

    Regression test for architectural changes to ensure both modes display
    the same content to users.
    """
    playbook_path = test_data_dir / "01-hello-playbooks.pb"

    # Run with streaming enabled (merge stderr into stdout to preserve ordering)
    result_streaming = subprocess.run(
        ["poetry", "run", "playbooks", "run", str(playbook_path), "--stream", "true"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=Path(__file__).parent.parent.parent,  # Project root
    )

    # Run with streaming disabled (merge stderr into stdout to preserve ordering)
    result_no_streaming = subprocess.run(
        ["poetry", "run", "playbooks", "run", str(playbook_path), "--stream", "false"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=Path(__file__).parent.parent.parent,  # Project root
    )

    # Both should succeed
    assert (
        result_streaming.returncode == 0
    ), f"Streaming mode failed: {result_streaming.stdout}"
    assert (
        result_no_streaming.returncode == 0
    ), f"Non-streaming mode failed: {result_no_streaming.stdout}"

    # Extract messages from both outputs (stderr is merged into stdout)
    streaming_output = result_streaming.stdout
    no_streaming_output = result_no_streaming.stdout
    messages_streaming = extract_messages_from_cli_output(streaming_output)
    messages_no_streaming = extract_messages_from_cli_output(no_streaming_output)

    # Print for debugging if test fails
    if messages_streaming != messages_no_streaming:
        print("\n=== STREAMING OUTPUT ===")
        print(result_streaming.stdout)
        print("\n=== NON-STREAMING OUTPUT ===")
        print(result_no_streaming.stdout)
        print("\n=== EXTRACTED MESSAGES (streaming) ===")
        for i, msg in enumerate(messages_streaming):
            print(f"{i}: {msg}")
        print("\n=== EXTRACTED MESSAGES (non-streaming) ===")
        for i, msg in enumerate(messages_no_streaming):
            print(f"{i}: {msg}")

    # Both modes should produce the same messages
    assert len(messages_streaming) == len(
        messages_no_streaming
    ), f"Different number of messages: streaming={len(messages_streaming)}, non-streaming={len(messages_no_streaming)}"

    # Compare each message (allowing for minor whitespace differences)
    for i, (msg_stream, msg_no_stream) in enumerate(
        zip(messages_streaming, messages_no_streaming)
    ):
        # Normalize whitespace for comparison
        normalized_stream = " ".join(msg_stream.split())
        normalized_no_stream = " ".join(msg_no_stream.split())
        assert (
            normalized_stream == normalized_no_stream
        ), f"Message {i} differs:\nStreaming: {msg_stream}\nNon-streaming: {msg_no_stream}"

    # Verify we got the expected messages
    assert len(messages_streaming) == 3, "Should have 3 messages from HelloWorldDemo"
    assert "Hello" in messages_streaming[0] and "playbooks" in messages_streaming[0]
    assert (
        "demo" in messages_streaming[1].lower()
        and "playbooks" in messages_streaming[1].lower()
    )
    assert "Goodbye" in messages_streaming[2] or "goodbye" in messages_streaming[2]


@pytest.mark.asyncio
async def test_example_15(test_data_dir, capsys):
    """Test that python-only playbook executes without any LLM calls."""

    playbooks = Playbooks([test_data_dir / "15-create-bgn.pb"])
    await playbooks.initialize()
    await playbooks.program.run_till_exit()

    assert len(playbooks.program.agents) == 5
    assert len(playbooks.program.agents_by_klass["B"]) == 2

    log = playbooks.program.agents_by_klass["A"][0].session_log.to_log_full()
    assert "from A" in log

    log = playbooks.program.agents_by_klass["B"][0].session_log.to_log_full()
    assert "from B" in log

    log = playbooks.program.agents_by_klass["B"][1].session_log.to_log_full()
    assert "from another B" in log

    log = playbooks.program.agents_by_klass["C"][0].session_log.to_log_full()
    assert "from C" in log


@pytest.mark.asyncio
async def test_example_16(test_data_dir):
    playbooks = Playbooks([test_data_dir / "16-variables.pb"])
    await playbooks.initialize()

    ai_agent = playbooks.program.agents[0]
    await playbooks.program.agents_by_id["human"].SendMessage(
        ai_agent.id, "checkers and blue"
    )
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, EOM)

    await playbooks.program.run_till_exit()
    log = ai_agent.session_log.to_log_full()
    print(log)
    assert re.search(r"Say.*John", log)
    assert re.search(r"Say.*Pinkerton", log)
    assert re.search(r"Say.*30", log)
    assert re.search(r"Say.*70", log)
    assert not re.search(r"Say.*male", log)
    assert re.search(r"Say.*Pinkerton.*blue.*checkers", log)
    assert re.search(r"Say.*India.*70", log)
    assert EXECUTION_FINISHED in log
