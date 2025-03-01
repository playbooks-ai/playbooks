import pytest

from playbooks.human_agent import HumanAgent


class TestHumanAgent:
    def test_initialization_default(self):
        agent = HumanAgent()
        assert agent.klass == "Human"

    def test_initialization_custom_class(self):
        agent = HumanAgent(klass="CustomHuman")
        assert agent.klass == "CustomHuman"

    def test_repr(self):
        agent = HumanAgent()
        assert repr(agent) == "User"

    def test_str(self):
        agent = HumanAgent()
        assert str(agent) == "User"

    def test_process_message_raises_not_implemented(self):
        agent = HumanAgent()
        with pytest.raises(NotImplementedError):
            list(
                agent.process_message(
                    message="Hello", from_agent=None, routing_type="direct"
                )
            )
