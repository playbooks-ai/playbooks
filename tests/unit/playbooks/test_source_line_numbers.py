"""Test source_line_number tracking on objects created from markdown."""

import pytest

from playbooks.agents.agent_builder import AgentBuilder
from playbooks.event_bus import EventBus
from playbooks.utils.markdown_to_ast import markdown_to_ast


def test_source_line_numbers_simple_playbook():
    """Test source_line_number on a simple playbook structure."""
    markdown_text = """# TestAgent
This is a test agent description.

## TestPlaybook() -> None
This is a test playbook description.

### Triggers
- T1:BGN At the beginning
- T2:CND When something happens

### Steps
- 01:YLD Ask the user for input
  - 01.01:EXE Process the input
- 02:RET Return the result

### Notes
- This is a note about the playbook
"""

    # Parse markdown to AST
    ast = markdown_to_ast(markdown_text)

    # Create agents from AST
    agents = AgentBuilder.create_agent_classes_from_ast(ast)
    assert len(agents) == 1

    # Create agent instance
    event_bus = EventBus("test_session")
    agent_class = agents.get("TestAgent")
    assert agent_class is not None
    agent = agent_class(event_bus)

    # Verify agent source_line_number
    assert agent.source_line_number == 1

    # Test playbook
    assert "TestPlaybook" in agent.playbooks
    playbook = agent.playbooks["TestPlaybook"]
    assert playbook.source_line_number == 4

    # Test triggers
    assert playbook.triggers is not None
    assert playbook.triggers.source_line_number == 7
    assert len(playbook.triggers.triggers) == 2

    # Test individual triggers
    trigger1 = playbook.triggers.triggers[0]
    assert trigger1.source_line_number == 8
    assert "T1:BGN At the beginning" == trigger1.trigger

    trigger2 = playbook.triggers.triggers[1]
    assert trigger2.source_line_number == 9
    assert "T2:CND When something happens" == trigger2.trigger

    # Test steps
    assert playbook.step_collection is not None
    assert len(playbook.step_collection.steps) == 3

    # Test individual steps
    step_01 = playbook.step_collection.get_step("01")
    assert step_01 is not None
    assert step_01.source_line_number == 12
    assert step_01.step_type == "YLD"
    assert step_01.content == "Ask the user for input"

    step_02 = playbook.step_collection.get_step("01.01")
    assert step_02 is not None
    assert step_02.source_line_number == 13
    assert step_02.step_type == "EXE"
    assert step_02.content == "Process the input"

    step_03 = playbook.step_collection.get_step("02")
    assert step_03 is not None
    assert step_03.source_line_number == 14
    assert step_03.step_type == "RET"
    assert step_03.content == "Return the result"


def test_source_line_numbers_builtin_playbooks():
    """Test that built-in playbooks have None for source_line_number."""
    markdown_text = """# TestAgent
This is a test agent.

## TestPlaybook() -> None
This is a test playbook.

### Triggers
- T1:BGN At the beginning

### Steps
- 01:RET Done
"""

    # Parse markdown to AST
    ast = markdown_to_ast(markdown_text)

    # Create agents from AST
    agents = AgentBuilder.create_agent_classes_from_ast(ast)
    agent_class = agents.get("TestAgent")
    assert agent_class is not None

    # Create agent instance
    event_bus = EventBus("test_session")
    agent = agent_class(event_bus)

    # Test built-in playbooks have source_line_number
    builtin_playbooks = [
        "SendMessage",
        "WaitForMessage",
        "Say",
        "SaveArtifact",
        "LoadArtifact",
    ]

    for playbook_name in builtin_playbooks:
        assert playbook_name in agent.playbooks
        playbook = agent.playbooks[playbook_name]
        assert playbook.source_line_number is not None

    # Test user-defined playbook has proper source_line_number
    user_playbook = agent.playbooks["TestPlaybook"]
    assert user_playbook.source_line_number == 4


def test_source_line_numbers_multi_agent_pbasm(test_data_dir):
    """Test source_line_number is set on all objects in multi-agent.pbasm."""
    # Read the actual multi-agent.pbasm file
    with open(test_data_dir / "multi-agent.pbasm", "r") as f:
        markdown_text = f.read()

    # Parse markdown to AST
    ast = markdown_to_ast(markdown_text)

    # Create agents from AST
    agents = AgentBuilder.create_agent_classes_from_ast(ast)
    assert len(agents) == 2

    # Create agent instances
    event_bus = EventBus("test_session")

    # Test FirstAgent
    first_agent_class = agents.get("FirstAgent")
    assert first_agent_class is not None
    first_agent = first_agent_class(event_bus)

    # Verify FirstAgent source_line_number
    assert first_agent.source_line_number == 1

    # Test FirstAgent playbooks
    assert "X" in first_agent.playbooks
    x_playbook = first_agent.playbooks["X"]
    assert x_playbook.source_line_number == 12

    # Test X playbook triggers
    assert x_playbook.triggers is not None
    assert x_playbook.triggers.source_line_number == 14
    assert len(x_playbook.triggers.triggers) == 1
    trigger = x_playbook.triggers.triggers[0]
    assert trigger.source_line_number == 15
    assert "T1:BGN" in trigger.trigger

    # Test X playbook steps
    assert x_playbook.step_collection is not None
    assert len(x_playbook.step_collection.steps) == 7

    # Steps are -
    # - 01:QUE Tell user about Canada's secret
    # - 02:QUE $population:float = GetCountryPopulation(country="India")
    # - 03:YLD call
    # - 04:EXE $result:float = $num * $population * 2
    # - 05:RET $result
    # Check individual steps
    step_01 = x_playbook.step_collection.get_step("01")
    assert step_01 is not None
    assert step_01.source_line_number == 17
    assert step_01.step_type == "QUE"
    assert step_01.content == "Get Canada's secret from the CountryInfo agent"

    step_02 = x_playbook.step_collection.get_step("02")
    assert step_02 is not None
    assert step_02.source_line_number == 18
    assert step_02.step_type == "YLD"
    assert step_02.content == "call"

    # Test CountryInfo agent
    country_info_class = agents.get("CountryInfo")
    assert country_info_class is not None
    country_info = country_info_class(event_bus)

    # Verify CountryInfo source_line_number
    assert country_info.source_line_number == 41

    # Test CountryInfo playbooks
    playbook_names = ["LocalPB", "GetCountryPopulation", "GetCountrySecret"]
    expected_line_numbers = [52, 58, 70]

    for name, expected_line in zip(playbook_names, expected_line_numbers):
        assert name in country_info.playbooks
        playbook = country_info.playbooks[name]
        assert playbook.source_line_number == expected_line

    # Test GetCountrySecret playbook in detail
    secret_playbook = country_info.playbooks["GetCountrySecret"]

    # Test triggers
    assert secret_playbook.triggers is not None
    assert secret_playbook.triggers.source_line_number == 75
    assert len(secret_playbook.triggers.triggers) == 1
    secret_trigger = secret_playbook.triggers.triggers[0]
    assert secret_trigger.source_line_number == 76

    # Test steps
    assert secret_playbook.step_collection is not None
    assert len(secret_playbook.step_collection.steps) == 1

    secret_step = secret_playbook.step_collection.get_step("01")
    assert secret_step is not None
    assert secret_step.source_line_number == 78
    assert secret_step.step_type == "RET"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
