import asyncio
import json
import re
from pathlib import Path
from typing import List

import frontmatter

from .agent_builder import AgentBuilder
from .debug.server import DebugServer
from .event_bus import EventBus
from .human_agent import HumanAgent
from .markdown_playbook_execution import ExecutionFinished
from .utils.markdown_to_ast import markdown_to_ast


class ProgramAgentsCommunicationMixin:
    async def route_message(
        self: "Program", sender_id: str, target_agent_id: str, message: str
    ):
        """Routes a message to the target agent's inbox queue."""
        target_agent = self.agents_by_id.get(target_agent_id)
        if not target_agent:
            return
        target_queue = target_agent.inboxes[sender_id]
        await target_queue.put(message)


class Program(ProgramAgentsCommunicationMixin):
    def __init__(
        self, full_program: str, event_bus: EventBus, program_paths: List[str] = None
    ):
        self.full_program = full_program
        self.event_bus = event_bus
        self.program_paths = program_paths or []
        self._debug_server = None

        self.extract_public_json()
        self.parse_metadata()
        self.ast = markdown_to_ast(self.program_content)
        self.agent_klasses = AgentBuilder.create_agents_from_ast(self.ast)
        self.agents = [klass(self.event_bus) for klass in self.agent_klasses.values()]
        if not self.agents:
            raise ValueError("No agents found in program")
        if len(self.agents) != len(self.public_jsons):
            raise ValueError(
                "Number of agents and public jsons must be the same. "
                f"Got {len(self.agents)} agents and {len(self.public_jsons)} public jsons"
            )

        self.update_metadata_from_agent(self.agents[0])

        for i in range(len(self.agents)):
            self.agents[i].public = self.public_jsons[i]
        self.agents.append(HumanAgent("human", self.event_bus))
        self.agents_by_klass = {}
        self.agents_by_id = {}
        for agent in self.agents:
            if agent.klass not in self.agents_by_klass:
                self.agents_by_klass[agent.klass] = []
            self.agents_by_klass[agent.klass].append(agent)
            self.agents_by_id[agent.id] = agent
            agent.program = self

    def _get_compiled_file_name(self) -> str:
        """Generate the compiled file name based on the first original file."""
        if self.program_paths:
            # Use the first file path as the base for the compiled file name
            first_file = Path(self.program_paths[0])
            return f"{first_file.stem}.pbc"
        return "unknown.pbc"

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
        frontmatter_data = frontmatter.loads(self.full_program)
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
        await asyncio.gather(*[agent.begin() for agent in self.agents])

    async def run_till_exit(self):
        try:
            await self.begin()
        except ExecutionFinished:
            pass

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
