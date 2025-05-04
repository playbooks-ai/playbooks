from playbooks.base_agent import BaseAgent


class HumanAgent(BaseAgent):
    def __init__(self, klass: str):
        super().__init__(klass)
        self.id = "human"

    async def begin(self):
        pass
