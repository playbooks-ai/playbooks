from unittest.mock import MagicMock, Mock

from playbooks.core.agents import Agent
from playbooks.core.message_router import MessageRouter, RoutingType
from playbooks.core.runtime import PlaybooksRuntime


def test_message_router_initialization():
    runtime = Mock(spec=PlaybooksRuntime)
    router = MessageRouter(runtime=runtime)
    assert router.runtime == runtime


def test_send_message_logs_message():
    runtime = Mock(spec=PlaybooksRuntime)
    from_agent = Mock(spec=Agent)
    from_agent.id = "from-agent-id"
    from_agent.klass = "from-agent-klass"
    from_agent.type = "from-agent-type"
    to_agent = Mock(spec=Agent)
    to_agent.id = "to-agent-id"
    to_agent.klass = "to-agent-klass"
    to_agent.type = "to-agent-type"
    to_agent.process_message = MagicMock(return_value=iter([]))

    router = MessageRouter(runtime=runtime)
    message = "Hello"

    # Call send_message
    list(router.send_message(message, from_agent, to_agent))

    # Assert that the message was logged
    assert runtime.add_runtime_log.called


def test_send_message_processes_message():
    runtime = Mock(spec=PlaybooksRuntime)
    from_agent = Mock(spec=Agent)
    from_agent.id = "from-agent-id"
    from_agent.klass = "from-agent-klass"
    from_agent.type = "from-agent-type"
    to_agent = Mock(spec=Agent)
    to_agent.id = "to-agent-id"
    to_agent.klass = "to-agent-klass"
    to_agent.type = "to-agent-type"
    to_agent.process_message = MagicMock(return_value=iter([]))

    router = MessageRouter(runtime=runtime)
    message = "Hello"

    # Call send_message
    list(router.send_message(message, from_agent, to_agent))

    # Assert that the message was processed
    to_agent.process_message.assert_called_once_with(
        message=message,
        from_agent=from_agent,
        routing_type=RoutingType.DIRECT,
        runtime=runtime,
    )
