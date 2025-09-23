import asyncio
import json
import logging
import re
from pathlib import Path

# Removed threading import - using asyncio only
from typing import Any, Dict, List, Type, Union

from playbooks.agents.base_agent import BaseAgent
from playbooks.constants import HUMAN_AGENT_KLASS
from playbooks.debug_logger import debug
from playbooks.utils import file_utils

from .agents import AIAgent, HumanAgent
from .agents.agent_builder import AgentBuilder
from .debug.server import (
    DebugServer,  # Note: Actually a debug client that connects to VSCode
)
from .event_bus import EventBus
from .events import ProgramTerminatedEvent
from .exceptions import ExecutionFinished, KlassNotFoundError
from .meetings import MeetingRegistry
from .message import Message, MessageType
from .utils.markdown_to_ast import markdown_to_ast
from .utils.spec_utils import SpecUtils

logger = logging.getLogger(__name__)


class AsyncAgentRuntime:
    """
    Asyncio-based runtime that manages agent execution.

    Uses asyncio tasks instead of threads for concurrent agent execution.
    """

    def __init__(self, program: "Program"):
        self.program = program
        self.agent_tasks: Dict[str, asyncio.Task] = {}
        self.running_agents: Dict[str, bool] = {}

    async def start_agent(self, agent):
        """Start an agent as an asyncio task."""
        if agent.id in self.running_agents and self.running_agents[agent.id]:
            return

        self.running_agents[agent.id] = True

        # debug("Starting agent", agent_id=agent.id, agent_type=agent.klass)

        task = asyncio.create_task(self._agent_main(agent))
        self.agent_tasks[agent.id] = task
        # Don't await - let it run independently
        return task

    async def stop_agent(self, agent_id: str):
        """Stop an agent gracefully."""
        if agent_id not in self.running_agents:
            return

        # debug("Stopping agent", agent_id=agent_id)

        # Signal shutdown
        self.running_agents[agent_id] = False

        # Cancel the task
        if agent_id in self.agent_tasks:
            task = self.agent_tasks[agent_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Notify debug server of agent termination
        if self.program._debug_server:
            await self.program._debug_server.send_thread_exited_event(agent_id)

        # Clean up
        self.agent_tasks.pop(agent_id, None)
        self.running_agents.pop(agent_id, None)

    async def stop_all_agents(self):
        """Stop all running agents."""
        agent_ids = list(self.running_agents.keys())
        for agent_id in agent_ids:
            await self.stop_agent(agent_id)

    async def _agent_main(self, agent):
        """Main coroutine for agent execution."""
        try:
            # Initialize and start the agent
            # await agent.initialize()
            if not self.program.execution_finished:
                await agent.begin()

        except ExecutionFinished as e:
            # Signal that execution is finished
            self.program.set_execution_finished(reason="normal", exit_code=0)
            debug(
                "Agent execution finished",
                agent_id=agent.id,
                agent_name=str(agent),
                reason=str(e),
            )
            # Don't re-raise ExecutionFinished to allow proper cleanup
            return
        except asyncio.CancelledError:
            debug(
                "Agent stopped",
                agent_id=agent.id,
                agent_name=str(agent),
                reason="cancelled",
            )

            raise
        except Exception as e:
            # Use structured logging for production errors (important for monitoring)
            logger.error(
                f"Fatal error in agent {agent.id}: {e}",
                extra={
                    "agent_id": agent.id,
                    "agent_name": str(agent),
                    "error_type": type(e).__name__,
                    "context": "agent_execution",
                },
                exc_info=True,
            )

            # Also use debug for developer troubleshooting
            debug(
                "Fatal agent error",
                agent_id=agent.id,
                agent_name=str(agent),
                error_type=type(e).__name__,
                error=str(e),
            )

            # Store the error on the agent for debugging
            agent._execution_error = e

            # Mark the program as having errors for test visibility
            self.program._has_agent_errors = True

            # Log agent error using error_utils for consistency
            from .utils.error_utils import log_agent_errors

            error_info = [
                {
                    "agent_id": agent.id,
                    "agent_name": str(agent),
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "error_obj": e,
                }
            ]
            log_agent_errors(error_info, "agent_runtime")

            raise
        finally:
            # Cleanup agent resources
            if hasattr(agent, "cleanup"):
                await agent.cleanup()


class ProgramAgentsCommunicationMixin:
    async def route_message(
        self: "Program",
        sender_id: str,
        sender_klass: str,
        receiver_spec: str,
        message: str,
        message_type: MessageType = MessageType.DIRECT,
        meeting_id: str = None,
    ):
        """Routes a message to receiver agent(s) via the runtime."""
        debug(
            "Routing message",
            sender_id=sender_id,
            receiver_spec=receiver_spec,
            message_type=message_type.value if message_type else None,
            message_length=len(message) if message else 0,
        )
        recipient_id = SpecUtils.extract_agent_id(receiver_spec)
        recipient = self.agents_by_id.get(recipient_id)
        recipient_klass = recipient.klass if recipient else None
        # Create simple message
        message = Message(
            sender_id=sender_id,
            sender_klass=sender_klass,
            content=message,
            recipient_klass=recipient_klass,
            recipient_id=recipient_id,
            message_type=message_type,
            meeting_id=meeting_id,
        )

        # First try to find by agent ID
        receiver_agent = self.agents_by_id.get(
            SpecUtils.extract_agent_id(receiver_spec)
        )
        debug(f"Receiver agent: {receiver_agent}")
        if receiver_agent:
            # Send to all agents using event-driven message handling
            debug(f"Sending message to receiver agent: {receiver_agent}")
            await receiver_agent._add_message_to_buffer(message)


class AgentIdRegistry:
    """Manages sequential agent ID generation."""

    def __init__(self):
        self._next_id = 1000

    def get_next_id(self) -> str:
        """Get the next sequential agent ID."""
        current_id = self._next_id
        self._next_id += 1
        return str(current_id)


class Program(ProgramAgentsCommunicationMixin):
    def __init__(
        self,
        event_bus: EventBus,
        program_paths: List[str] = None,
        compiled_program_paths: List[str] = None,
        program_content: str = None,
        metadata: dict = {},
    ):
        self.metadata = metadata
        self.event_bus = event_bus

        self.program_paths = program_paths or []
        self.compiled_program_paths = compiled_program_paths or []
        self.program_content = program_content
        if self.compiled_program_paths and self.program_content:
            raise ValueError(
                "Both compiled_program_paths and program_content cannot be provided."
            )
        if not self.compiled_program_paths and not self.program_content:
            raise ValueError(
                "Either compiled_program_paths or program_content must be provided."
            )

        self._debug_server = None
        self.agent_id_registry = AgentIdRegistry()
        self.meeting_id_registry = MeetingRegistry()

        # Agent runtime manages execution with asyncio
        self.runtime = AsyncAgentRuntime(program=self)

        self.extract_public_json()
        self.parse_metadata()

        self.agent_klasses = {}

        if self.program_content:
            # Using program content directly (no cache file)
            ast = markdown_to_ast(self.program_content)
            self.agent_klasses.update(AgentBuilder.create_agent_classes_from_ast(ast))
        else:
            # Using compiled program paths (cache files)
            for i, markdown_content in enumerate(self.markdown_contents):
                cache_file_path = self.compiled_program_paths[i]
                # Convert to absolute path for consistent tracking
                abs_cache_path = str(Path(cache_file_path).resolve())
                ast = markdown_to_ast(markdown_content, source_file_path=abs_cache_path)
                self.agent_klasses.update(
                    AgentBuilder.create_agent_classes_from_ast(ast)
                )

        self.agents = []
        self.agents_by_klass = {}
        self.agents_by_id = {}

        self.execution_finished = False
        self.initialized = False
        self._has_agent_errors = (
            False  # Track if any agents have had errors for test visibility
        )

    async def initialize(self):
        self.agents = [
            await self.create_agent(klass)
            for klass in self.agent_klasses.values()
            if klass.should_create_instance_at_start()
        ]
        if len(self.agent_klasses) != len(self.public_jsons):
            raise ValueError(
                "Number of agents and public jsons must be the same. "
                f"Got {len(self.agent_klasses)} agents and {len(self.public_jsons)} public jsons"
            )

        agent_klass_list = list(self.agent_klasses.values())
        for i in range(len(agent_klass_list)):
            agent_klass = agent_klass_list[i]
            agent_klass.public_json = self.public_jsons[i]
            if agent_klass.public_json:
                for playbook in agent_klass.playbooks.values():
                    if not playbook.description:
                        playbook_jsons = list(
                            filter(
                                lambda x: x["name"] == playbook.klass,
                                agent_klass.public_json,
                            )
                        )
                        if playbook_jsons:
                            playbook.description = playbook_jsons[0].get(
                                "description", ""
                            )

        self.agents.append(
            HumanAgent(
                klass=HUMAN_AGENT_KLASS,
                agent_id="human",
                program=self,
                event_bus=self.event_bus,
            )
        )

        # Agent registration
        for agent in self.agents:
            if agent.klass not in self.agents_by_klass:
                self.agents_by_klass[agent.klass] = []
            self.agents_by_klass[agent.klass].append(agent)
            self.agents_by_id[agent.id] = agent
            agent.program = self

        self.event_agents_changed()
        self.initialized = True

    @property
    def markdown_contents(self) -> List[str]:
        if self.program_content:
            return [self.program_content]
        return [file_utils.read_file(path) for path in self.compiled_program_paths]

    def event_agents_changed(self):
        for agent in self.agents:
            if isinstance(agent, AIAgent):
                agent.event_agents_changed()

    async def create_agent(self, agent_klass: Union[str, Type[BaseAgent]], **kwargs):
        if isinstance(agent_klass, str):
            klass = self.agent_klasses.get(agent_klass)
            if not klass:
                raise ValueError(f"Agent class {agent_klass} not found")
        else:
            klass = agent_klass

        agent = klass(
            self.event_bus,
            self.agent_id_registry.get_next_id(),
            program=self,
        )
        agent.kwargs = kwargs

        # Agent registration (no locking needed in single-threaded asyncio)
        self.agents.append(agent)
        if agent.klass not in self.agents_by_klass:
            self.agents_by_klass[agent.klass] = []
        self.agents_by_klass[agent.klass].append(agent)
        self.agents_by_id[agent.id] = agent
        agent.program = self

        self.event_agents_changed()
        if self._debug_server:
            await self._debug_server.send_thread_started_event(agent.id)

        return agent

    async def _start_new_agent(self, agent):
        """Initialize and start a newly created agent."""
        try:
            # Start agent as asyncio task
            await self.runtime.start_agent(agent)
        except Exception as e:
            # Log error with full stack trace and re-raise to prevent silent failures
            logger.error(
                f"Error initializing new agent {agent.id}: {str(e)}", exc_info=True
            )
            debug("Agent initialization error", agent_id=agent.id, error=str(e))
            # Store the error on the agent for debugging
            agent._initialization_error = e
            # Re-raise to ensure the caller knows about the failure
            raise RuntimeError(
                f"Failed to initialize agent {agent.id}: {str(e)}"
            ) from e

    def _get_compiled_file_name(self) -> str:
        """Generate the compiled file name based on the first original file."""
        return self.compiled_program_paths[0]

    def _emit_compiled_program_event(self):
        """Emit an event with the compiled program content for debugging."""
        from .events import CompiledProgramEvent

        compiled_file_path = self._get_compiled_file_name()
        event = CompiledProgramEvent(
            session_id="program",
            compiled_file_path=compiled_file_path,
            content=file_utils.read_file(compiled_file_path),
            original_file_paths=self.program_paths,
        )
        self.event_bus.publish(event)

    def parse_metadata(self):
        self.title = self.metadata.get("title", None)
        self.description = self.metadata.get("description", None)

    def extract_public_json(self):
        # Extract publics.json from full_program
        self.public_jsons = []

        for markdown_content in self.markdown_contents:
            matches = re.findall(
                r"(```public\.json(.*?)```)", markdown_content, re.DOTALL
            )
            if matches:
                for match in matches:
                    public_json = json.loads(match[1])
                    self.public_jsons.append(public_json)
                    markdown_content = markdown_content.replace(match[0], "")

    async def begin(self):
        # Start all agents as asyncio tasks concurrently
        # Use task creation instead of gather to let them run independently
        tasks = []
        for agent in self.agents:
            await agent.initialize()
        for agent in self.agents:
            task = await self.runtime.start_agent(agent)
            if task:  # Only append if a task was created
                tasks.append(task)
        # Don't wait for tasks - let them run independently

    async def run_till_exit(self):
        if not self.initialized:
            raise ValueError("Program not initialized. Call initialize() first.")
        try:
            # Create the execution completion event before starting agents
            self.execution_finished_event = asyncio.Event()

            # If debugging with stop-on-entry, wait for continue before starting execution
            # if self._debug_server and self._debug_server.stop_on_entry:
            #     # Wait for the continue command from the debug server
            #     # NOTE: wait_for_continue now requires agent_id parameter
            #     await self._debug_server.wait_for_continue(agent_id="default")

            await self.begin()
            # Wait for ExecutionFinished to be raised from any agent thread
            # Agent threads are designed to run indefinitely until this exception
            await self.execution_finished_event.wait()
        except ExecutionFinished:
            self.set_execution_finished(reason="normal", exit_code=0)
        except Exception as e:
            logger.error(
                f"Unexpected error in run_till_exit: {e}",
                exc_info=True,
                extra={"context": "program_execution", "error_type": type(e).__name__},
            )
            debug(
                "Unexpected run_till_exit error",
                error=str(e),
                error_type=type(e).__name__,
            )
            self.set_execution_finished(reason="error", exit_code=1)
            raise
        finally:
            await self.shutdown()

    def get_agent_errors(self) -> List[Dict[str, Any]]:
        """Get a list of all agent errors that have occurred.

        Returns:
            List of error dictionaries with agent_id, error, and error_type
        """
        errors = []
        for agent in self.agents:
            if hasattr(agent, "_execution_error"):
                errors.append(
                    {
                        "agent_id": agent.id,
                        "agent_name": str(agent),
                        "error": str(agent._execution_error),
                        "error_type": type(agent._execution_error).__name__,
                        "error_obj": agent._execution_error,
                    }
                )
            if hasattr(agent, "_initialization_error"):
                errors.append(
                    {
                        "agent_id": agent.id,
                        "agent_name": str(agent),
                        "error": str(agent._initialization_error),
                        "error_type": type(agent._initialization_error).__name__,
                        "error_obj": agent._initialization_error,
                    }
                )
        return errors

    def has_agent_errors(self) -> bool:
        """Check if any agents have had errors."""
        return self._has_agent_errors or len(self.get_agent_errors()) > 0

    def set_execution_finished(self, reason: str = "normal", exit_code: int = 0):
        self.execution_finished = True
        if hasattr(self, "execution_finished_event"):
            self.execution_finished_event.set()
        if self.event_bus:
            termination_event = ProgramTerminatedEvent(
                session_id="program", reason=reason, exit_code=exit_code
            )
            self.event_bus.publish(termination_event)

    async def shutdown(self):
        """Shutdown all agents and clean up resources."""
        self.set_execution_finished(reason="normal", exit_code=0)

        # Stop all agent tasks via runtime
        await self.runtime.stop_all_agents()

        # Shutdown debug server if running
        await self.shutdown_debug_server()

    async def start_debug_server(
        self, host: str = "127.0.0.1", port: int = 7529, stop_on_entry: bool = False
    ) -> None:
        """Start debug client to connect to VSCode debug adapter."""
        # debug(
        #     f"Program.start_debug_server() called with host={host}, port={port}, stop_on_entry={stop_on_entry}",
        # )
        if self._debug_server is None:
            # debug("Creating new DebugServer instance...")
            self._debug_server = DebugServer(program=self, host=host, port=port)

            # Set stop-on-entry flag before starting server
            self._debug_server.set_stop_on_entry(stop_on_entry)
            # debug(f"Stop-on-entry flag set to: {stop_on_entry}")

            # debug("Starting debug server...")
            await self._debug_server.start()

            # Create and connect debug handler AFTER the server has started and socket is connected
            from .debug.debug_handler import DebugHandler

            # debug(
            #     f"[DEBUG] Creating debug handler after server start, client_socket exists: {self._debug_server.client_socket is not None}",
            # )
            debug_handler = DebugHandler(self._debug_server)
            self._debug_server.set_debug_handler(debug_handler)
            # debug("Debug handler created and connected to debug server")

            # Store reference to this program in the debug client
            self._debug_server.set_program(self)

            # Register the program's event bus with the debug client
            self._debug_server.register_bus(self.event_bus)

            for agent in self.agents:
                await self._debug_server.send_thread_started_event(agent.id)
        else:
            debug("Debug server already exists, skipping creation")

    async def shutdown_debug_server(self) -> None:
        """Shutdown the debug client if it's running."""
        if self._debug_server:
            try:
                await self._debug_server.shutdown()
            except Exception as e:
                debug("Error shutting down debug server", error=str(e))
            finally:
                self._debug_server = None

    # Meeting Management Methods

    def get_agents_by_specs(self, specs: List[str]) -> List[BaseAgent]:
        """Get agents by specs."""
        try:
            return [
                self.agents_by_id[SpecUtils.extract_agent_id(spec)] for spec in specs
            ]
        except KeyError:
            pass

        # Try to get agents by name
        agents = []
        for agent in self.agents:
            name = agent.kwargs.get("name")

            if name and name in specs:
                agents.append(agent)

        if agents and len(agents) == len(specs):
            return agents

        raise ValueError(f"Agent not found. Specs: {specs}")

    def get_agent_by_klass(self, klass: str) -> BaseAgent:
        if klass in ["human", "user", "HUMAN", "USER"]:
            klass = HUMAN_AGENT_KLASS
        try:
            return self.agents_by_klass[klass]
        except KeyError as e:
            raise ValueError(f"Agent with klass {e} not found")

    async def get_agents_by_klasses(self, klasses: List[str]) -> List[BaseAgent]:
        """Get agents by klasses.

        If an agent with a given klass does not exist, it will be created.

        Returns:
            List[BaseAgent]: List of agents found or created for each provided klass.

        Raises:
            KlassNotFoundError: If any klass is not a known klass.
            ValueError: If all provided classes are known klasses
        """
        agents = []
        # Check if all klasses are valid
        for klass in klasses:
            if klass not in self.agent_klasses.keys():
                raise KlassNotFoundError(f"Agent klass {klass} not found")

        # Create agents for any klasses that don't exist
        for klass in klasses:
            if (
                klass not in self.agents_by_klass.keys()
                or not self.agents_by_klass[klass]
            ):
                # If at least one agent does not exist for a klass, create an instance
                await self.create_agent(klass)

            agents.append(self.agents_by_klass[klass][0])

        return agents

    async def get_agents_by_klasses_or_specs(
        self, klasses_or_specs: List[str]
    ) -> List[BaseAgent]:
        """Get agents by specs or klasses."""
        try:
            agents = await self.get_agents_by_klasses(klasses_or_specs)
        except KlassNotFoundError:
            # If any klass is not a known klass, try to get agents by specs
            agents = self.get_agents_by_specs(klasses_or_specs)
        return agents
