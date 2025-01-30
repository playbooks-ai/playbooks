class BaseAgent:
    def __init__(self, klass: str):
        self.klass = klass

    def process_message(
        self,
        message: str,
        from_agent: "BaseAgent",
        routing_type: str,
        llm_config: dict = None,
        stream: bool = False,
    ):
        raise NotImplementedError
