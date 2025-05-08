import asyncio
import json
import re

import frontmatter

from .agent_builder import AgentBuilder
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
    def __init__(self, full_program: str):
        self.full_program = full_program
        self.extract_public_json()
        self.parse_metadata()
        self.ast = markdown_to_ast(self.program_content)
        self.agent_klasses = AgentBuilder.create_agents_from_ast(self.ast)
        self.agents = [klass() for klass in self.agent_klasses.values()]
        if not self.agents:
            raise ValueError("No agents found in program")
        if len(self.agents) != len(self.public_jsons):
            raise ValueError(
                "Number of agents and public jsons must be the same. "
                f"Got {len(self.agents)} agents and {len(self.public_jsons)} public jsons"
            )
        for i in range(len(self.agents)):
            self.agents[i].public = self.public_jsons[i]
        self.agents.append(HumanAgent("human"))
        self.agents_by_klass = {}
        self.agents_by_id = {}
        for agent in self.agents:
            if agent.klass not in self.agents_by_klass:
                self.agents_by_klass[agent.klass] = []
            self.agents_by_klass[agent.klass].append(agent)
            self.agents_by_id[agent.id] = agent
            agent.program = self

    def parse_metadata(self):
        frontmatter_data = frontmatter.loads(self.full_program)
        self.metadata = frontmatter_data.metadata
        self.title = frontmatter_data.get("title", "Untitled Program")
        self.description = frontmatter_data.get("description", "")
        self.application = frontmatter_data.get("application", "MultiAgentChat")
        self.program_content = frontmatter_data.content

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
