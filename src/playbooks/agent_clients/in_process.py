from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playbooks.ai_agent import AIAgent


class InProcessPlaybooksAgentClient:
    def __init__(self, agent: "AIAgent"):
        self.agent = agent

    async def execute_playbook(self, playbook_klass: str, args, kwargs):
        return await self.agent.execute_playbook(playbook_klass, args, kwargs)
