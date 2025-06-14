from .agents import BaseAgent


class SystemAgent(BaseAgent):
    def __init__(self):
        super().__init__("SystemAgent")
