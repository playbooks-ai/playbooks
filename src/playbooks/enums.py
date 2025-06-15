from enum import Enum


class AgentType(str, Enum):
    HUMAN = "human"
    AI = "ai"


class RoutingType(str, Enum):
    DIRECT = "direct"
    BROADCAST = "broadcast"


class LLMMessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
