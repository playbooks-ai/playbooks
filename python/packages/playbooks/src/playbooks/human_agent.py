from .base_agent import BaseAgent


class HumanAgent(BaseAgent):
    def __init__(self, klass: str = "Human"):
        super().__init__(klass)

    def process_message(
        self,
        message: str,
        from_agent: "BaseAgent",
        routing_type: str,
        llm_config: dict = None,
        stream: bool = False,
    ):
        # We don't know yet what it means for human agent to receive a message
        raise NotImplementedError
