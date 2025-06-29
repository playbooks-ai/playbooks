import asyncio
import json
import queue
import re
import threading
from pathlib import Path
from typing import Dict, List

import frontmatter
from yaml.scanner import ScannerError

from .agent_builder import AgentBuilder
from .agents import AIAgent, HumanAgent
from .debug.server import DebugServer
from .event_bus import EventBus
from .exceptions import ExecutionFinished
from .meetings import MeetingRegistry
from .simple_message import SimpleMessage
from .utils.markdown_to_ast import markdown_to_ast


class AgentRuntime:
    """
    Runtime that manages agent execution.

    Responsible for creating threads, managing message queues, and coordinating execution.
    Agents focus on behavior, runtime focuses on execution.
    """

    def __init__(self):
        self.agent_threads: Dict[str, threading.Thread] = {}
        self.agent_queues: Dict[str, queue.Queue] = {}
        self.agent_shutdown_events: Dict[str, threading.Event] = {}
        self.running_agents: Dict[str, bool] = {}

    def start_agent(self, agent):
        """Start an agent in its own thread."""
        if agent.id in self.running_agents and self.running_agents[agent.id]:
            return

        # Create thread infrastructure for this agent
        message_queue = queue.Queue()
        shutdown_event = threading.Event()

        self.agent_queues[agent.id] = message_queue
        self.agent_shutdown_events[agent.id] = shutdown_event
        self.running_agents[agent.id] = True

        # Create and start thread
        thread = threading.Thread(
            target=self._agent_thread_main,
            args=(agent, message_queue, shutdown_event),
            daemon=True,
        )
        self.agent_threads[agent.id] = thread
        thread.start()

    def stop_agent(self, agent_id: str):
        """Stop an agent gracefully."""
        if agent_id not in self.running_agents:
            return

        # Signal shutdown
        self.running_agents[agent_id] = False
        if agent_id in self.agent_shutdown_events:
            self.agent_shutdown_events[agent_id].set()

        # Wait for thread to finish
        if agent_id in self.agent_threads:
            thread = self.agent_threads[agent_id]
            if thread.is_alive():
                thread.join(timeout=5.0)

        # Clean up
        self.agent_threads.pop(agent_id, None)
        self.agent_queues.pop(agent_id, None)
        self.agent_shutdown_events.pop(agent_id, None)
        self.running_agents.pop(agent_id, None)

    def stop_all_agents(self):
        """Stop all running agents."""
        agent_ids = list(self.running_agents.keys())
        for agent_id in agent_ids:
            self.stop_agent(agent_id)

    def send_message_to_agent(self, agent_id: str, message):
        """Send a message to an agent's queue."""
        if agent_id in self.agent_queues:
            self.agent_queues[agent_id].put(message)

    def _agent_thread_main(self, agent, message_queue, shutdown_event):
        """Main function for agent thread."""
        # Create async loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Initialize and start the agent
            loop.run_until_complete(agent.initialize())
            loop.run_until_complete(agent.begin())

            # Main message processing loop
            while (
                self.running_agents.get(agent.id, False) and not shutdown_event.is_set()
            ):
                try:
                    # Poll for messages with timeout
                    message = message_queue.get(timeout=0.1)
                    if message:
                        loop.run_until_complete(agent.process_message(message))
                except queue.Empty:
                    continue  # Keep polling
                except Exception as e:
                    print(f"Error processing message in {agent.id}: {e}")

        except Exception as e:
            print(f"Fatal error in agent {agent.id} thread: {e}")
        finally:
            loop.close()


class ProgramAgentsCommunicationMixin:
    def route_message(
        self: "Program",
        sender_id: str,
        target_spec: str,
        message: str,
        message_type: str = "direct",
        meeting_id: str = None,
    ):
        """Routes a message to target agent(s) via the runtime."""
        # Create simple message
        simple_message = SimpleMessage(
            sender_id=sender_id,
            content=message,
            message_type=message_type,
            meeting_id=meeting_id,
        )

        # Thread-safe access to agent registry
        with self.agents_lock:
            # First try to find by agent ID
            target_agent = self.agents_by_id.get(target_spec)
            if target_agent:
                if target_agent.id == "human":
                    # Send to human agent via runtime thread
                    self.runtime.send_message_to_agent(target_agent.id, simple_message)
                else:
                    # Send to AI agent directly to message buffer
                    target_agent._message_buffer.append(simple_message)
                return

            # If not found by ID, try by class name and send to all agents of that class
            agents_by_class = self.agents_by_klass.get(target_spec, [])
            for agent in agents_by_class:
                if agent.id == "human":
                    self.runtime.send_message_to_agent(agent.id, simple_message)
                else:
                    agent._message_buffer.append(simple_message)


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
        self, full_program: str, event_bus: EventBus, program_paths: List[str] = None
    ):
        self.full_program = full_program
        self.event_bus = event_bus
        self.program_paths = program_paths or []
        self._debug_server = None
        self.agent_id_registry = AgentIdRegistry()
        self.meeting_id_registry = MeetingRegistry()

        # Thread-safe agent registry
        self.agents_lock = threading.RLock()

        # Agent runtime manages execution
        self.runtime = AgentRuntime()

        self.extract_public_json()
        self.parse_metadata()
        self.ast = markdown_to_ast(self.program_content)
        self.agent_klasses = AgentBuilder.create_agents_from_ast(self.ast)
        self.agents = [
            klass(
                self.event_bus,
                self.agent_id_registry.get_next_id(),
                program=self,
            )
            for klass in self.agent_klasses.values()
        ]
        if not self.agents:
            raise ValueError("No agents found in program")
        if len(self.agents) != len(self.public_jsons):
            raise ValueError(
                "Number of agents and public jsons must be the same. "
                f"Got {len(self.agents)} agents and {len(self.public_jsons)} public jsons"
            )
        self.update_metadata_from_agent(self.agents[0])

        for i in range(len(self.agents)):
            agent = self.agents[i]
            agent.public_json = self.public_jsons[i]
            if agent.public_json:
                for playbook in agent.playbooks.values():
                    if not playbook.description:
                        playbook_jsons = list(
                            filter(
                                lambda x: x["name"] == playbook.klass,
                                agent.public_json,
                            )
                        )
                        if playbook_jsons:
                            playbook.description = playbook_jsons[0].get(
                                "description", ""
                            )

        self.agents.append(
            HumanAgent(
                klass="Human", agent_id="human", program=self, event_bus=self.event_bus
            )
        )
        self.agents_by_klass = {}
        self.agents_by_id = {}

        # Thread-safe agent registration
        with self.agents_lock:
            for agent in self.agents:
                if agent.klass not in self.agents_by_klass:
                    self.agents_by_klass[agent.klass] = []
                self.agents_by_klass[agent.klass].append(agent)
                self.agents_by_id[agent.id] = agent
                agent.program = self

        # No complex message processor needed - agents handle their own queues

        self.event_agents_changed()

    def event_agents_changed(self):
        for agent in self.agents:
            if isinstance(agent, AIAgent):
                agent.event_agents_changed()

    async def create_agent(self, agent_klass: str, **kwargs):
        klass = self.agent_klasses.get(agent_klass)
        if not klass:
            raise ValueError(f"Agent class {agent_klass} not found")

        agent = klass(self.event_bus, self.agent_id_registry.get_next_id())
        agent.kwargs = kwargs

        # Thread-safe agent registration
        with self.agents_lock:
            self.agents.append(agent)
            if agent.klass not in self.agents_by_klass:
                self.agents_by_klass[agent.klass] = []
            self.agents_by_klass[agent.klass].append(agent)
            self.agents_by_id[agent.id] = agent
            agent.program = self

        # No message processor to update

        self.event_agents_changed()

        # Initialize and start the agent synchronously to avoid race conditions
        await self._initialize_new_agent(agent)

        return agent.to_dict()

    async def _initialize_new_agent(self, agent):
        """Initialize and start a newly created agent."""
        try:
            await agent.initialize()
            await agent.begin()
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
        try:
            frontmatter_data = frontmatter.loads(self.full_program)
        except ScannerError:
            self.metadata = {}
            self.title = None
            self.description = None
            self.application = "MultiAgentChat"
            self.program_content = self.full_program
            return

        self.metadata = frontmatter_data.metadata
        self.title = frontmatter_data.get("title", None)
        self.description = frontmatter_data.get("description", None)
        self.application = frontmatter_data.get("application", "MultiAgentChat")
        self.program_content = frontmatter_data.content

    def update_metadata_from_agent(self, agent):
        if not self.title:
            self.title = agent.klass
        if not self.description:
            self.description = agent.description

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
        # Hybrid approach: only thread the human agent, run AI agents synchronously
        for agent in self.agents:
            if agent.id == "human":
                # Start human agent in thread for message processing
                self.runtime.start_agent(agent)
            else:
                # Initialize AI agents synchronously but don't start threads
                await agent.initialize()

        # Start AI agents synchronously
        ai_agents = [agent for agent in self.agents if agent.id != "human"]
        await asyncio.gather(*[agent.begin() for agent in ai_agents])

    async def run_till_exit(self):
        try:
            await self.begin()
        except ExecutionFinished:
            pass
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Shutdown all agents and clean up resources."""
        # Stop all agent threads via runtime
        self.runtime.stop_all_agents()

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

    def find_meeting_owner(self, meeting_id: str):
        """Find the agent who owns/created a meeting.

        Args:
            meeting_id: ID of the meeting

        Returns:
            Agent who owns the meeting, or None if not found
        """
        owner_id = self.meeting_id_registry.get_meeting_owner(meeting_id)
        if owner_id:
            return self.agents_by_id.get(owner_id)
        return None
