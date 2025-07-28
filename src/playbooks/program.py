import asyncio
import json
import re

# Removed threading import - using asyncio only
from pathlib import Path
from typing import Dict, List, Type, Union

from playbooks.agents.base_agent import BaseAgent
from playbooks.constants import EXECUTION_FINISHED, HUMAN_AGENT_KLASS

from .agents import AIAgent, HumanAgent
from .agents.agent_builder import AgentBuilder
from .debug.server import DebugServer
from .event_bus import EventBus
from .exceptions import ExecutionFinished, KlassNotFoundError
from .meetings import MeetingRegistry
from .message import Message, MessageType
from .utils.markdown_to_ast import markdown_to_ast
from .utils.spec_utils import SpecUtils


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

        # Create and start asyncio task
        task = asyncio.create_task(self._agent_main(agent))
        self.agent_tasks[agent.id] = task
        # Don't await - let it run independently
        return task

    async def stop_agent(self, agent_id: str):
        """Stop an agent gracefully."""
        if agent_id not in self.running_agents:
            return

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
            self.program.set_execution_finished()
            print(f"Agent {agent.id} {EXECUTION_FINISHED}: {e}")
            raise e
        except asyncio.CancelledError:
            print(f"Agent {agent.id} was cancelled")
            raise
        except Exception as e:
            print(f"Fatal error in agent {agent.id}: {e}")
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
        if receiver_agent:
            # Send to all agents using event-driven message handling
            await receiver_agent._add_message_to_buffer(message)

        # # If not found by ID, try by class name and send to all agents of that class
        # agents_by_class = self.agents_by_klass.get(receiver_spec, [])
        # for agent in agents_by_class:
        #     # Send to all agents using event-driven message handling
        #     agent._add_message_to_buffer(message)


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
        full_program: str,
        event_bus: EventBus,
        program_paths: List[str] = None,
        metadata: dict = {},
    ):
        self.full_program = full_program
        self.metadata = metadata
        self.event_bus = event_bus
        self.program_paths = program_paths or []
        self._debug_server = None
        self.agent_id_registry = AgentIdRegistry()
        self.meeting_id_registry = MeetingRegistry()

        # Agent runtime manages execution with asyncio
        self.runtime = AsyncAgentRuntime(program=self)

        self.extract_public_json()
        self.parse_metadata()
        self.ast = markdown_to_ast(self.full_program)
        self.agent_klasses = AgentBuilder.create_agent_classes_from_ast(self.ast)

        self.agents = []
        self.agents_by_klass = {}
        self.agents_by_id = {}

        self.execution_finished = False
        self.initialized = False

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

        return agent

    async def _start_new_agent(self, agent):
        """Initialize and start a newly created agent."""
        try:
            # Start agent as asyncio task
            await self.runtime.start_agent(agent)
        except Exception as e:
            # Log error but don't crash the program
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error initializing new agent {agent.id}: {str(e)}")

    def _get_compiled_file_name(self) -> str:
        """Generate the compiled file name based on the first original file."""
        if self.program_paths:
            # Use the first file path as the base for the compiled file name
            first_file = Path(self.program_paths[0])
            return f"{first_file.stem}.pbasm"
        return "unknown.pbasm"

    def _emit_compiled_program_event(self):
        """Emit an event with the compiled program content for debugging."""
        from .events import CompiledProgramEvent

        compiled_file_path = self._get_compiled_file_name()
        event = CompiledProgramEvent(
            compiled_file_path=compiled_file_path,
            content=self.full_program,
            original_file_paths=self.program_paths,
        )
        self.event_bus.publish(event)

    def parse_metadata(self):
        self.title = self.metadata.get("title", None)
        self.description = self.metadata.get("description", None)

    def extract_public_json(self):
        # Extract publics.json from full_program
        self.public_jsons = []
        matches = re.findall(r"(```public\.json(.*?)```)", self.full_program, re.DOTALL)
        if matches:
            for match in matches:
                public_json = json.loads(match[1])
                self.public_jsons.append(public_json)
                self.full_program = self.full_program.replace(match[0], "")

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
            await self.begin()
            # Wait for ExecutionFinished to be raised from any agent thread
            # Agent threads are designed to run indefinitely until this exception
            await self.execution_finished_event.wait()
        except ExecutionFinished:
            self.set_execution_finished()
        finally:
            await self.shutdown()

    def set_execution_finished(self):
        self.execution_finished = True
        if hasattr(self, "execution_finished_event"):
            self.execution_finished_event.set()

    async def shutdown(self):
        """Shutdown all agents and clean up resources."""
        self.set_execution_finished()

        # Stop all agent tasks via runtime
        await self.runtime.stop_all_agents()

        # Shutdown debug server if running
        await self.shutdown_debug_server()

    async def start_debug_server(
        self, host: str = "127.0.0.1", port: int = 5678
    ) -> None:
        """Start a debug server to stream runtime events.

        The debug server connects to the agents' event buses to receive and stream events.

        Args:
            host: Host address to listen on
            port: Port to listen on
        """
        if self._debug_server is None:
            self._debug_server = DebugServer(host, port)
            await self._debug_server.start()

            # Store reference to this program in the debug server
            self._debug_server.set_program(self)

            # Register all agents' buses with the debug server
            for agent in self.agents:
                if hasattr(agent, "state") and hasattr(agent.state, "event_bus"):
                    self._debug_server.register_bus(agent.state.event_bus)

            # Emit compiled program content for debugging
            self._emit_compiled_program_event()

    async def shutdown_debug_server(self) -> None:
        """Shutdown the debug server if it's running."""
        if self._debug_server:
            await self._debug_server.shutdown()
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
