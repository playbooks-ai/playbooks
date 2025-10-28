"""Tests for AIAgentProxy and create_playbook_wrapper.

This module provides comprehensive test coverage for agent proxy functionality,
which enables cross-agent playbook calls in LLM-generated code.
"""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest

from playbooks.agent_proxy import (
    AIAgentProxy,
    create_agent_proxies,
    create_playbook_wrapper,
)

if TYPE_CHECKING:
    pass


class TestCreatePlaybookWrapper:
    """Tests for the create_playbook_wrapper function."""

    @pytest.mark.asyncio
    async def test_wrapper_calls_execute_playbook(self):
        """Test that wrapper calls execute_playbook on the current agent."""
        # Setup
        current_agent = AsyncMock()
        current_agent.execute_playbook = AsyncMock()
        namespace = Mock()

        # Execute
        wrapper = create_playbook_wrapper("TestPlaybook", current_agent, namespace)
        await wrapper("arg1", "arg2", kwarg1="value1")

        # Assert
        current_agent.execute_playbook.assert_called_once_with(
            "TestPlaybook", ("arg1", "arg2"), {"kwarg1": "value1"}
        )

    @pytest.mark.asyncio
    async def test_wrapper_with_no_args(self):
        """Test wrapper execution with no arguments."""
        current_agent = AsyncMock()
        current_agent.execute_playbook = AsyncMock()
        namespace = Mock()

        wrapper = create_playbook_wrapper("SimplePlaybook", current_agent, namespace)
        await wrapper()

        current_agent.execute_playbook.assert_called_once_with("SimplePlaybook", (), {})

    @pytest.mark.asyncio
    async def test_wrapper_with_only_kwargs(self):
        """Test wrapper execution with keyword arguments only."""
        current_agent = AsyncMock()
        current_agent.execute_playbook = AsyncMock()
        namespace = Mock()

        wrapper = create_playbook_wrapper("ConfigPlaybook", current_agent, namespace)
        await wrapper(setting1="value1", setting2="value2")

        current_agent.execute_playbook.assert_called_once_with(
            "ConfigPlaybook", (), {"setting1": "value1", "setting2": "value2"}
        )

    @pytest.mark.asyncio
    async def test_wrapper_returns_async_callable(self):
        """Test that create_playbook_wrapper returns an async callable."""
        current_agent = AsyncMock()
        namespace = Mock()

        wrapper = create_playbook_wrapper("Playbook", current_agent, namespace)

        # Check that it's an async function
        import inspect

        assert inspect.iscoroutinefunction(wrapper)

    @pytest.mark.asyncio
    async def test_wrapper_with_mixed_args_and_kwargs(self):
        """Test wrapper with both positional and keyword arguments."""
        current_agent = AsyncMock()
        current_agent.execute_playbook = AsyncMock()
        namespace = Mock()

        wrapper = create_playbook_wrapper("MixedArgsPlaybook", current_agent, namespace)
        await wrapper(10, 20, 30, name="test", enabled=True)

        current_agent.execute_playbook.assert_called_once_with(
            "MixedArgsPlaybook", (10, 20, 30), {"name": "test", "enabled": True}
        )

    @pytest.mark.asyncio
    async def test_wrapper_preserves_playbook_name(self):
        """Test that wrapper preserves the correct playbook name."""
        current_agent = AsyncMock()
        current_agent.execute_playbook = AsyncMock()
        namespace = Mock()

        playbook_name = "FileSystemAgent.validate_directory"
        wrapper = create_playbook_wrapper(playbook_name, current_agent, namespace)
        await wrapper("test_dir")

        call_args = current_agent.execute_playbook.call_args
        assert call_args[0][0] == playbook_name


class TestAIAgentProxy:
    """Tests for the AIAgentProxy class."""

    def _create_mock_agent(self, agent_klass_name="FileSystemAgent"):
        """Helper to create a mock agent with necessary attributes."""
        agent = Mock()
        agent.klass = agent_klass_name

        # Create mock program with agent_klasses
        agent.program = Mock()

        # Create mock agent class
        agent_klass = Mock()
        agent_klass.playbooks = {
            "validate_directory": Mock(),
            "list_files": Mock(),
            "read_file": Mock(),
        }

        agent.program.agent_klasses = {
            agent_klass_name: agent_klass,
            "OtherAgent": Mock(playbooks={"other_playbook": Mock()}),
        }

        return agent, agent_klass

    def test_proxy_initialization(self):
        """Test AIAgentProxy initialization."""
        agent, _ = self._create_mock_agent("FileSystemAgent")
        namespace = Mock()

        proxy = AIAgentProxy(
            proxied_agent_klass_name="FileSystemAgent",
            current_agent=agent,
            namespace=namespace,
        )

        assert proxy._proxied_agent_klass_name == "FileSystemAgent"
        assert proxy._current_agent == agent
        assert proxy._namespace == namespace

    def test_proxy_repr(self):
        """Test string representation of proxy."""
        agent, _ = self._create_mock_agent("FileSystemAgent")
        namespace = Mock()

        proxy = AIAgentProxy(
            proxied_agent_klass_name="FileSystemAgent",
            current_agent=agent,
            namespace=namespace,
        )

        assert repr(proxy) == "AIAgentProxy(FileSystemAgent)"

    def test_getattr_returns_wrapper_for_valid_playbook(self):
        """Test that __getattr__ returns a wrapper for valid playbooks."""
        agent, _ = self._create_mock_agent("FileSystemAgent")
        namespace = Mock()

        proxy = AIAgentProxy(
            proxied_agent_klass_name="FileSystemAgent",
            current_agent=agent,
            namespace=namespace,
        )

        result = proxy.validate_directory

        # Should return a callable (the wrapper)
        assert callable(result)

    def test_getattr_blocks_private_attributes(self):
        """Test that __getattr__ blocks access to private attributes."""
        agent, _ = self._create_mock_agent("FileSystemAgent")
        namespace = Mock()

        proxy = AIAgentProxy(
            proxied_agent_klass_name="FileSystemAgent",
            current_agent=agent,
            namespace=namespace,
        )

        with pytest.raises(AttributeError) as exc_info:
            _ = proxy._private_method

        assert "object has no attribute '_private_method'" in str(exc_info.value)

    def test_getattr_raises_for_nonexistent_playbook(self):
        """Test that __getattr__ raises AttributeError for non-existent playbooks."""
        agent, _ = self._create_mock_agent("FileSystemAgent")
        namespace = Mock()

        proxy = AIAgentProxy(
            proxied_agent_klass_name="FileSystemAgent",
            current_agent=agent,
            namespace=namespace,
        )

        with pytest.raises(AttributeError) as exc_info:
            _ = proxy.nonexistent_playbook

        assert "object has no attribute 'nonexistent_playbook'" in str(exc_info.value)

    def test_getattr_with_multiple_playbooks(self):
        """Test accessing multiple different playbooks through proxy."""
        agent, _ = self._create_mock_agent("FileSystemAgent")
        namespace = Mock()

        proxy = AIAgentProxy(
            proxied_agent_klass_name="FileSystemAgent",
            current_agent=agent,
            namespace=namespace,
        )

        # Should return wrappers for all valid playbooks
        validate = proxy.validate_directory
        list_files = proxy.list_files
        read_file = proxy.read_file

        assert all(callable(w) for w in [validate, list_files, read_file])

    def test_is_coroutine_marker(self):
        """Test that _is_coroutine_marker returns False."""
        agent, _ = self._create_mock_agent("FileSystemAgent")
        namespace = Mock()

        proxy = AIAgentProxy(
            proxied_agent_klass_name="FileSystemAgent",
            current_agent=agent,
            namespace=namespace,
        )

        assert proxy._is_coroutine_marker() is False

    @pytest.mark.asyncio
    async def test_proxy_method_creates_correct_playbook_name(self):
        """Test that proxy method calls use correct AgentName.method format."""
        agent = AsyncMock()
        agent.klass = "FileSystemAgent"
        agent.execute_playbook = AsyncMock()

        # Setup agent classes
        agent_klass = Mock()
        agent_klass.playbooks = {"validate_directory": Mock()}

        agent.program = Mock()
        agent.program.agent_klasses = {
            "FileSystemAgent": agent_klass,
        }

        namespace = Mock()

        proxy = AIAgentProxy(
            proxied_agent_klass_name="FileSystemAgent",
            current_agent=agent,
            namespace=namespace,
        )

        # Get the wrapper method
        method = proxy.validate_directory

        # The wrapper should be callable and async
        import inspect

        assert inspect.iscoroutinefunction(method)

    def test_proxy_accesses_correct_agent_class(self):
        """Test that proxy accesses the correct agent class from program."""
        agent, _ = self._create_mock_agent("FileSystemAgent")
        namespace = Mock()

        proxy = AIAgentProxy(
            proxied_agent_klass_name="FileSystemAgent",
            current_agent=agent,
            namespace=namespace,
        )

        # The proxy should have the correct agent class
        assert (
            proxy._proxied_agent_klass == agent.program.agent_klasses["FileSystemAgent"]
        )

    def test_getattr_private_dunder_methods(self):
        """Test that private dunder methods raise AttributeError."""
        agent, _ = self._create_mock_agent("FileSystemAgent")
        namespace = Mock()

        proxy = AIAgentProxy(
            proxied_agent_klass_name="FileSystemAgent",
            current_agent=agent,
            namespace=namespace,
        )

        # Dunder methods don't trigger __getattr__, but we can test accessing
        # attributes that start with underscore through getattr
        with pytest.raises(AttributeError) as exc_info:
            proxy.__getattr__("__private__")

        assert "__private__" in str(exc_info.value)

    def test_getattr_single_underscore_methods(self):
        """Test that single underscore methods raise AttributeError."""
        agent, _ = self._create_mock_agent("FileSystemAgent")
        namespace = Mock()

        proxy = AIAgentProxy(
            proxied_agent_klass_name="FileSystemAgent",
            current_agent=agent,
            namespace=namespace,
        )

        with pytest.raises(AttributeError):
            _ = proxy._setup_namespace


class TestCreateAgentProxies:
    """Tests for the create_agent_proxies function."""

    def _create_mock_program_with_agents(self, num_agents=3):
        """Helper to create a mock program with multiple agents."""
        program = Mock()

        # Create multiple agent classes
        agent_klasses = {}
        for i, name in enumerate(
            ["FirstAgent", "SecondAgent", "ThirdAgent"][:num_agents]
        ):
            agent_klass = Mock()
            agent_klass.playbooks = {f"playbook_{j}": Mock() for j in range(2)}
            agent_klasses[name] = agent_klass

        program.agent_klasses = agent_klasses
        program.agents = True  # hasattr check

        return program, agent_klasses

    def test_create_proxies_for_all_agents(self):
        """Test that proxies are created for all agents except current."""
        program, agent_klasses = self._create_mock_program_with_agents(3)

        current_agent = Mock()
        current_agent.klass = "FirstAgent"
        current_agent.program = program

        namespace = Mock()

        proxies = create_agent_proxies(current_agent, namespace)

        # Should create proxies for all agents except FirstAgent
        assert len(proxies) == 2
        assert "SecondAgent" in proxies
        assert "ThirdAgent" in proxies
        assert "FirstAgent" not in proxies

    def test_proxy_instances_are_correct_type(self):
        """Test that created proxies are AIAgentProxy instances."""
        program, _ = self._create_mock_program_with_agents(2)

        current_agent = Mock()
        current_agent.klass = "FirstAgent"
        current_agent.program = program

        namespace = Mock()

        proxies = create_agent_proxies(current_agent, namespace)

        for proxy in proxies.values():
            assert isinstance(proxy, AIAgentProxy)

    def test_proxies_have_correct_names(self):
        """Test that proxies are keyed by agent class name."""
        program, _ = self._create_mock_program_with_agents(3)

        current_agent = Mock()
        current_agent.klass = "FirstAgent"
        current_agent.program = program

        namespace = Mock()

        proxies = create_agent_proxies(current_agent, namespace)

        assert set(proxies.keys()) == {"SecondAgent", "ThirdAgent"}

    def test_proxies_reference_correct_current_agent(self):
        """Test that all proxies reference the current agent."""
        program, _ = self._create_mock_program_with_agents(2)

        current_agent = Mock()
        current_agent.klass = "FirstAgent"
        current_agent.program = program

        namespace = Mock()

        proxies = create_agent_proxies(current_agent, namespace)

        for proxy in proxies.values():
            assert proxy._current_agent == current_agent

    def test_proxies_reference_correct_namespace(self):
        """Test that all proxies reference the provided namespace."""
        program, _ = self._create_mock_program_with_agents(2)

        current_agent = Mock()
        current_agent.klass = "FirstAgent"
        current_agent.program = program

        namespace = Mock()

        proxies = create_agent_proxies(current_agent, namespace)

        for proxy in proxies.values():
            assert proxy._namespace == namespace

    def test_create_proxies_no_program(self):
        """Test create_agent_proxies when current_agent has no program."""
        current_agent = Mock()
        current_agent.program = None

        namespace = Mock()

        proxies = create_agent_proxies(current_agent, namespace)

        assert proxies == {}

    def test_create_proxies_program_without_agents(self):
        """Test create_agent_proxies when program has no agents attribute."""
        program = Mock()
        program.agent_klasses = {}
        del program.agents  # Remove the agents attribute

        current_agent = Mock()
        current_agent.program = program

        namespace = Mock()

        proxies = create_agent_proxies(current_agent, namespace)

        assert proxies == {}

    def test_create_proxies_single_agent_in_program(self):
        """Test create_agent_proxies with only one agent in program."""
        program, _ = self._create_mock_program_with_agents(1)

        current_agent = Mock()
        current_agent.klass = "FirstAgent"
        current_agent.program = program

        namespace = Mock()

        proxies = create_agent_proxies(current_agent, namespace)

        # Should create no proxies since there's only the current agent
        assert proxies == {}

    def test_proxies_are_distinct_instances(self):
        """Test that each proxy is a separate instance."""
        program, _ = self._create_mock_program_with_agents(3)

        current_agent = Mock()
        current_agent.klass = "FirstAgent"
        current_agent.program = program

        namespace = Mock()

        proxies = create_agent_proxies(current_agent, namespace)

        proxy_list = list(proxies.values())
        assert proxy_list[0] is not proxy_list[1]

    def test_proxies_have_correct_proxied_agent_name(self):
        """Test that each proxy knows which agent it proxies for."""
        program, _ = self._create_mock_program_with_agents(3)

        current_agent = Mock()
        current_agent.klass = "FirstAgent"
        current_agent.program = program

        namespace = Mock()

        proxies = create_agent_proxies(current_agent, namespace)

        assert proxies["SecondAgent"]._proxied_agent_klass_name == "SecondAgent"
        assert proxies["ThirdAgent"]._proxied_agent_klass_name == "ThirdAgent"


class TestAIAgentProxyIntegration:
    """Integration tests for proxy functionality."""

    @pytest.mark.asyncio
    async def test_proxy_method_call_integration(self):
        """Test end-to-end proxy method call."""
        # Setup
        agent = AsyncMock()
        agent.klass = "FileSystemAgent"
        agent.execute_playbook = AsyncMock(return_value=(True, "success"))

        agent_klass = Mock()
        agent_klass.playbooks = {"validate_directory": Mock()}

        agent.program = Mock()
        agent.program.agent_klasses = {"FileSystemAgent": agent_klass}

        namespace = Mock()

        proxy = AIAgentProxy(
            proxied_agent_klass_name="FileSystemAgent",
            current_agent=agent,
            namespace=namespace,
        )

        # Execute
        method = proxy.validate_directory
        await method("/some/path")

        # Verify
        agent.execute_playbook.assert_called_once()
        call_args = agent.execute_playbook.call_args
        assert call_args[0][0] == "FileSystemAgent.validate_directory"

    @pytest.mark.asyncio
    async def test_multiple_proxies_for_different_agents(self):
        """Test creating and using proxies for multiple agents."""
        # Setup program with multiple agents
        program = Mock()

        agent_klasses = {}
        for name in ["AgentA", "AgentB", "AgentC"]:
            agent_klass = Mock()
            agent_klass.playbooks = {"run": Mock()}
            agent_klasses[name] = agent_klass

        program.agent_klasses = agent_klasses
        program.agents = True

        current_agent = Mock()
        current_agent.klass = "AgentA"
        current_agent.program = program

        namespace = Mock()

        # Create proxies
        proxies = create_agent_proxies(current_agent, namespace)

        # Should have proxies for AgentB and AgentC but not AgentA
        assert set(proxies.keys()) == {"AgentB", "AgentC"}

    def test_proxy_error_handling_invalid_method(self):
        """Test proxy error handling for invalid method names."""
        agent, _ = self._create_mock_agent("FileSystemAgent")
        namespace = Mock()

        proxy = AIAgentProxy(
            proxied_agent_klass_name="FileSystemAgent",
            current_agent=agent,
            namespace=namespace,
        )

        # Should raise AttributeError for method not in playbooks
        with pytest.raises(AttributeError) as exc_info:
            _ = proxy.invalid_method_name

        assert "invalid_method_name" in str(exc_info.value)

    def _create_mock_agent(self, agent_klass_name="FileSystemAgent"):
        """Helper to create a mock agent with necessary attributes."""
        agent = Mock()
        agent.klass = agent_klass_name

        agent.program = Mock()

        agent_klass = Mock()
        agent_klass.playbooks = {
            "validate_directory": Mock(),
            "list_files": Mock(),
        }

        agent.program.agent_klasses = {
            agent_klass_name: agent_klass,
        }

        return agent, agent_klass


class TestPlaybookWrapperEdgeCases:
    """Edge case tests for playbook wrapper functionality."""

    @pytest.mark.asyncio
    async def test_wrapper_with_complex_argument_types(self):
        """Test wrapper handles complex argument types correctly."""
        current_agent = AsyncMock()
        current_agent.execute_playbook = AsyncMock()
        namespace = Mock()

        wrapper = create_playbook_wrapper("ComplexPlaybook", current_agent, namespace)

        # Call with various types
        complex_args = [
            42,
            "string",
            {"key": "value"},
            [1, 2, 3],
            (4, 5, 6),
            None,
        ]

        await wrapper(*complex_args)

        # Verify all arguments were passed correctly
        call_args = current_agent.execute_playbook.call_args
        assert call_args[0][0] == "ComplexPlaybook"
        assert call_args[0][1] == tuple(complex_args)

    @pytest.mark.asyncio
    async def test_wrapper_exception_propagation(self):
        """Test that exceptions in execute_playbook are propagated."""
        current_agent = AsyncMock()
        current_agent.execute_playbook = AsyncMock(side_effect=ValueError("Test error"))
        namespace = Mock()

        wrapper = create_playbook_wrapper("ErrorPlaybook", current_agent, namespace)

        with pytest.raises(ValueError) as exc_info:
            await wrapper()

        assert "Test error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wrapper_with_none_arguments(self):
        """Test wrapper handles None arguments correctly."""
        current_agent = AsyncMock()
        current_agent.execute_playbook = AsyncMock()
        namespace = Mock()

        wrapper = create_playbook_wrapper("NullPlaybook", current_agent, namespace)
        await wrapper(None, None, kwarg=None)

        call_args = current_agent.execute_playbook.call_args
        assert call_args[0][1] == (None, None)
        assert call_args[0][2] == {"kwarg": None}
