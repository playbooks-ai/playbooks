from pathlib import Path

import pytest

from playbooks.agent_factory import AgentFactory
from playbooks.config import LLMConfig
from playbooks.exceptions import PlaybookError


def test_create_agents(test_data_dir):
    agents = AgentFactory.from_playbooks_paths(
        [test_data_dir / "example.md"], LLMConfig()
    )

    assert len(agents) == 1
    assert list(agents.keys())[0] == "HelloWorld Agent"


def test_create_agents_file_not_found():
    with pytest.raises(PlaybookError) as exc_info:
        AgentFactory.from_playbooks_paths([Path("/nonexistent/file.md")], LLMConfig())
    assert "No files found" in str(exc_info.value)


def test_create_agents_invalid_playbook(test_data_dir, tmp_path):
    invalid_playbook = tmp_path / "invalid.md"
    invalid_playbook.write_text(
        "# Invalid Playbook\n\nThis is not a valid playbook format"
    )

    with pytest.raises(PlaybookError) as exc_info:
        AgentFactory.from_playbooks_paths([invalid_playbook], LLMConfig())
    assert "Failed to parse playbook" in str(exc_info.value)
