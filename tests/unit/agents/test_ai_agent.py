from unittest.mock import Mock, patch

from playbooks.agents.ai_agent import AIAgent
from playbooks.infrastructure.event_bus import EventBus
from playbooks.playbook.python_playbook import PythonPlaybook


def create_mock_playbook(name: str, has_begin_trigger: bool = True):
    """Helper function to create a mock playbook with begin trigger."""
    playbook_mock = Mock()
    playbook_mock.configure_mock(
        name=name, triggers=Mock(triggers=[Mock(is_begin=has_begin_trigger)])
    )
    return playbook_mock


class MockAIAgent(AIAgent):
    klass = "MockAIAgent"
    description = "Mock AIAgent"
    metadata = {}
    playbooks = {}
    namespace_manager = None

    def __init__(self):
        super().__init__(Mock(spec=EventBus))

    async def discover_playbooks(self):
        pass


def test_create_begin_playbook_no_bgn_playbooks():
    """Test create_begin_playbook when there are no BGN playbooks."""
    agent = MockAIAgent()
    agent.create_begin_playbook()
    assert agent.bgn_playbook_name is not None


def test_create_begin_playbook_one_bgn_playbook():
    """Test create_begin_playbook when there is one BGN playbook."""
    agent = MockAIAgent()
    playbook = create_mock_playbook("Main")
    agent.playbooks = {"Main": playbook}
    agent.create_begin_playbook()
    assert agent.bgn_playbook_name is not None


@patch.object(PythonPlaybook, "create_playbooks_from_code_block")
def test_create_begin_playbook_multiple_bgn_playbooks(mock_create_playbooks):
    """Test create_begin_playbook when there are multiple BGN playbooks."""
    mock_create_playbooks.return_value = {"Begin": Mock()}

    agent = MockAIAgent()
    playbook1 = create_mock_playbook("Main")
    playbook2 = create_mock_playbook("Main2")
    agent.playbooks = {"Main": playbook1, "Main2": playbook2}

    agent.create_begin_playbook()
    assert agent.bgn_playbook_name is not None
