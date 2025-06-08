from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playbooks.ai_agent import AIAgent


class InProcessPlaybooksAgentClient:
    def __init__(self, agent: "AIAgent"):
        self.agent = agent

    async def execute_playbook(self, playbook_klass: str, args, kwargs):
        new_agent_instance = self.agent.program.agent_klasses[self.agent.klass](
            self.agent.program.event_bus
        )
        new_agent_instance.program = self.agent.program
        new_agent_instance.set_up_agent_clients()
        return await new_agent_instance.execute_playbook(playbook_klass, args, kwargs)
