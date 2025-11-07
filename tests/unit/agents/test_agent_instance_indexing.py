"""Test agent instance indexing for targeting specific agents in cross-agent calls."""

from unittest.mock import Mock

import pytest

from playbooks.agent_proxy import AIAgentInstanceProxy, AIAgentProxy
from playbooks.agents.local_ai_agent import LocalAIAgent


class TestResolveTargetAgent:
    """Test the _resolve_target_agent method."""

    def test_resolve_without_dot_returns_none(self):
        """Test that playbook names without dots return None."""
        agent = Mock(spec=LocalAIAgent)
        agent.program = Mock()
        agent.program.agents = []

        # Bind the actual method to the mock
        agent._resolve_target_agent = LocalAIAgent._resolve_target_agent.__get__(
            agent, LocalAIAgent
        )

        target_agent, playbook_name = agent._resolve_target_agent("SimplePlaybook")

        assert target_agent is None
        assert playbook_name is None

    def test_resolve_without_program_returns_none(self):
        """Test that resolution without a program returns None."""
        agent = Mock(spec=LocalAIAgent)
        agent.program = None

        # Bind the actual method to the mock
        agent._resolve_target_agent = LocalAIAgent._resolve_target_agent.__get__(
            agent, LocalAIAgent
        )

        target_agent, playbook_name = agent._resolve_target_agent("Agent.Playbook")

        assert target_agent is None
        assert playbook_name is None

    def test_resolve_agent_class_only(self):
        """Test resolving AgentName.PlaybookName format (first instance)."""
        # Create mock agents
        agent1 = Mock()
        agent1.klass = "TestAgent"
        agent1.id = "agent1"

        agent2 = Mock()
        agent2.klass = "TestAgent"
        agent2.id = "agent2"

        agent3 = Mock()
        agent3.klass = "OtherAgent"
        agent3.id = "agent3"

        # Create the calling agent
        calling_agent = Mock(spec=LocalAIAgent)
        calling_agent.program = Mock()
        calling_agent.program.agents = [agent1, agent2, agent3]

        # Bind the actual method to the mock
        calling_agent._resolve_target_agent = (
            LocalAIAgent._resolve_target_agent.__get__(calling_agent, LocalAIAgent)
        )

        target_agent, playbook_name = calling_agent._resolve_target_agent(
            "TestAgent.DoSomething"
        )

        assert target_agent is agent1  # Should return first instance
        assert playbook_name == "DoSomething"

    def test_resolve_specific_agent_instance(self):
        """Test resolving AgentName:AgentId.PlaybookName format."""
        # Create mock agents
        agent1 = Mock()
        agent1.klass = "TestAgent"
        agent1.id = "agent1"

        agent2 = Mock()
        agent2.klass = "TestAgent"
        agent2.id = "agent2"

        agent3 = Mock()
        agent3.klass = "TestAgent"
        agent3.id = "agent3"

        # Create the calling agent
        calling_agent = Mock(spec=LocalAIAgent)
        calling_agent.program = Mock()
        calling_agent.program.agents = [agent1, agent2, agent3]

        # Bind the actual method to the mock
        calling_agent._resolve_target_agent = (
            LocalAIAgent._resolve_target_agent.__get__(calling_agent, LocalAIAgent)
        )

        # Should target agent2 specifically
        target_agent, playbook_name = calling_agent._resolve_target_agent(
            "TestAgent:agent2.DoSomething"
        )

        assert target_agent is agent2
        assert playbook_name == "DoSomething"

    def test_resolve_nonexistent_agent_class(self):
        """Test resolving with non-existent agent class."""
        agent1 = Mock()
        agent1.klass = "TestAgent"
        agent1.id = "agent1"

        calling_agent = Mock(spec=LocalAIAgent)
        calling_agent.program = Mock()
        calling_agent.program.agents = [agent1]

        calling_agent._resolve_target_agent = (
            LocalAIAgent._resolve_target_agent.__get__(calling_agent, LocalAIAgent)
        )

        target_agent, playbook_name = calling_agent._resolve_target_agent(
            "NonExistent.DoSomething"
        )

        assert target_agent is None
        assert playbook_name == "DoSomething"

    def test_resolve_nonexistent_agent_instance(self):
        """Test resolving with non-existent agent instance ID."""
        agent1 = Mock()
        agent1.klass = "TestAgent"
        agent1.id = "agent1"

        calling_agent = Mock(spec=LocalAIAgent)
        calling_agent.program = Mock()
        calling_agent.program.agents = [agent1]

        calling_agent._resolve_target_agent = (
            LocalAIAgent._resolve_target_agent.__get__(calling_agent, LocalAIAgent)
        )

        target_agent, playbook_name = calling_agent._resolve_target_agent(
            "TestAgent:nonexistent.DoSomething"
        )

        assert target_agent is None
        assert playbook_name == "DoSomething"

    def test_resolve_with_complex_playbook_name(self):
        """Test resolving with playbook names containing dots."""
        agent1 = Mock()
        agent1.klass = "TestAgent"
        agent1.id = "agent1"

        calling_agent = Mock(spec=LocalAIAgent)
        calling_agent.program = Mock()
        calling_agent.program.agents = [agent1]

        calling_agent._resolve_target_agent = (
            LocalAIAgent._resolve_target_agent.__get__(calling_agent, LocalAIAgent)
        )

        # First dot separates agent from playbook
        target_agent, playbook_name = calling_agent._resolve_target_agent(
            "TestAgent.Some.Complex.Name"
        )

        assert target_agent is agent1
        assert playbook_name == "Some.Complex.Name"


class TestAgentProxyIndexing:
    """Test the AIAgentProxy indexing functionality."""

    def test_agent_proxy_getitem_returns_instance_proxy(self):
        """Test that proxy[id] returns an AIAgentInstanceProxy."""
        # Create mock objects
        current_agent = Mock(spec=LocalAIAgent)
        namespace = Mock()

        # Mock agent class
        mock_agent_klass = Mock()
        mock_agent_klass.playbooks = {}

        current_agent.program = Mock()
        current_agent.program.agent_klasses = {"TestAgent": mock_agent_klass}

        proxy = AIAgentProxy("TestAgent", current_agent, namespace)
        instance_proxy = proxy["agent123"]

        assert isinstance(instance_proxy, AIAgentInstanceProxy)
        assert instance_proxy._target_agent_id == "agent123"
        assert instance_proxy._proxied_agent_klass_name == "TestAgent"

    def test_agent_instance_proxy_repr(self):
        """Test the string representation of AIAgentInstanceProxy."""
        current_agent = Mock(spec=LocalAIAgent)
        namespace = Mock()

        mock_agent_klass = Mock()
        mock_agent_klass.playbooks = {}

        current_agent.program = Mock()
        current_agent.program.agent_klasses = {"TestAgent": mock_agent_klass}

        proxy = AIAgentProxy("TestAgent", current_agent, namespace)
        instance_proxy = proxy["my_agent"]

        assert repr(instance_proxy) == "AIAgentInstanceProxy(TestAgent['my_agent'])"

    def test_agent_proxy_repr(self):
        """Test the string representation of AIAgentProxy."""
        current_agent = Mock(spec=LocalAIAgent)
        namespace = Mock()

        mock_agent_klass = Mock()
        mock_agent_klass.playbooks = {}

        current_agent.program = Mock()
        current_agent.program.agent_klasses = {"TestAgent": mock_agent_klass}

        proxy = AIAgentProxy("TestAgent", current_agent, namespace)

        assert repr(proxy) == "AIAgentProxy(TestAgent)"

    def test_agent_instance_proxy_has_coroutine_marker(self):
        """Test that AIAgentInstanceProxy has the coroutine marker method."""
        current_agent = Mock(spec=LocalAIAgent)
        namespace = Mock()

        mock_agent_klass = Mock()
        mock_agent_klass.playbooks = {}

        current_agent.program = Mock()
        current_agent.program.agent_klasses = {"TestAgent": mock_agent_klass}

        proxy = AIAgentProxy("TestAgent", current_agent, namespace)
        instance_proxy = proxy["agent1"]

        assert hasattr(instance_proxy, "_is_coroutine_marker")
        assert instance_proxy._is_coroutine_marker() is False

    def test_agent_proxy_getattr_creates_wrapper(self):
        """Test that accessing a playbook method creates a wrapper."""
        current_agent = Mock(spec=LocalAIAgent)
        namespace = Mock()

        mock_agent_klass = Mock()
        mock_agent_klass.playbooks = {"TestPlaybook": Mock()}

        current_agent.program = Mock()
        current_agent.program.agent_klasses = {"TestAgent": mock_agent_klass}

        proxy = AIAgentProxy("TestAgent", current_agent, namespace)
        wrapper = proxy.TestPlaybook

        assert callable(wrapper)

    def test_agent_instance_proxy_getattr_creates_wrapper_with_id(self):
        """Test that instance proxy creates wrapper with agent ID."""
        current_agent = Mock(spec=LocalAIAgent)
        namespace = Mock()

        mock_agent_klass = Mock()
        mock_agent_klass.playbooks = {"TestPlaybook": Mock()}

        current_agent.program = Mock()
        current_agent.program.agent_klasses = {"TestAgent": mock_agent_klass}

        proxy = AIAgentProxy("TestAgent", current_agent, namespace)
        instance_proxy = proxy["agent123"]
        wrapper = instance_proxy.TestPlaybook

        assert callable(wrapper)

    def test_agent_proxy_getattr_raises_for_nonexistent_playbook(self):
        """Test that accessing non-existent playbook raises AttributeError."""
        current_agent = Mock(spec=LocalAIAgent)
        namespace = Mock()

        mock_agent_klass = Mock()
        mock_agent_klass.playbooks = {}

        current_agent.program = Mock()
        current_agent.program.agent_klasses = {"TestAgent": mock_agent_klass}

        proxy = AIAgentProxy("TestAgent", current_agent, namespace)

        with pytest.raises(AttributeError):
            _ = proxy.NonExistentPlaybook

    def test_agent_instance_proxy_getattr_raises_for_nonexistent_playbook(self):
        """Test that instance proxy raises AttributeError for non-existent playbook."""
        current_agent = Mock(spec=LocalAIAgent)
        namespace = Mock()

        mock_agent_klass = Mock()
        mock_agent_klass.playbooks = {}

        current_agent.program = Mock()
        current_agent.program.agent_klasses = {"TestAgent": mock_agent_klass}

        proxy = AIAgentProxy("TestAgent", current_agent, namespace)
        instance_proxy = proxy["agent1"]

        with pytest.raises(AttributeError):
            _ = instance_proxy.NonExistentPlaybook

    def test_agent_proxy_getattr_raises_for_private_attributes(self):
        """Test that accessing private attributes raises AttributeError."""
        current_agent = Mock(spec=LocalAIAgent)
        namespace = Mock()

        mock_agent_klass = Mock()
        mock_agent_klass.playbooks = {}

        current_agent.program = Mock()
        current_agent.program.agent_klasses = {"TestAgent": mock_agent_klass}

        proxy = AIAgentProxy("TestAgent", current_agent, namespace)

        with pytest.raises(AttributeError):
            _ = proxy._private_method

    def test_agent_instance_proxy_getattr_raises_for_private_attributes(self):
        """Test that instance proxy raises AttributeError for private attributes."""
        current_agent = Mock(spec=LocalAIAgent)
        namespace = Mock()

        mock_agent_klass = Mock()
        mock_agent_klass.playbooks = {}

        current_agent.program = Mock()
        current_agent.program.agent_klasses = {"TestAgent": mock_agent_klass}

        proxy = AIAgentProxy("TestAgent", current_agent, namespace)
        instance_proxy = proxy["agent1"]

        with pytest.raises(AttributeError):
            _ = instance_proxy._private_method


class TestPlaybookWrapperExecution:
    """Test the playbook wrapper execution with agent targeting."""

    @pytest.mark.asyncio
    async def test_wrapper_calls_without_agent_id(self):
        """Test that wrapper without agent ID calls execute_playbook normally."""
        from playbooks.agent_proxy import create_playbook_wrapper

        current_agent = Mock(spec=LocalAIAgent)
        namespace = Mock()

        # Mock execute_playbook to return success
        async def mock_execute(playbook_name, args, kwargs):
            return (True, "result")

        current_agent.execute_playbook = mock_execute

        wrapper = create_playbook_wrapper(
            "TestAgent.DoSomething", current_agent, namespace
        )
        result = await wrapper(1, 2, key="value")

        assert result == "result"

    @pytest.mark.asyncio
    async def test_wrapper_calls_with_agent_id(self):
        """Test that wrapper with agent ID formats playbook name correctly."""
        from playbooks.agent_proxy import create_playbook_wrapper

        current_agent = Mock(spec=LocalAIAgent)
        namespace = Mock()

        called_playbook_name = None

        # Mock execute_playbook to capture the playbook name
        async def mock_execute(playbook_name, args, kwargs):
            nonlocal called_playbook_name
            called_playbook_name = playbook_name
            return (True, "result")

        current_agent.execute_playbook = mock_execute

        wrapper = create_playbook_wrapper(
            "TestAgent.DoSomething",
            current_agent,
            namespace,
            target_agent_id="agent123",
        )
        result = await wrapper(1, 2, key="value")

        assert result == "result"
        assert called_playbook_name == "TestAgent:agent123.DoSomething"

    @pytest.mark.asyncio
    async def test_wrapper_handles_error(self):
        """Test that wrapper handles execution errors correctly."""
        from playbooks.agent_proxy import create_playbook_wrapper

        current_agent = Mock(spec=LocalAIAgent)
        namespace = Mock()

        # Mock execute_playbook to return error
        async def mock_execute(playbook_name, args, kwargs):
            return (False, "Something went wrong")

        current_agent.execute_playbook = mock_execute

        wrapper = create_playbook_wrapper(
            "TestAgent.DoSomething", current_agent, namespace
        )
        result = await wrapper()

        assert result == "ERROR: Something went wrong"
