from enum import Enum


# AgentType enum
class AgentType:
    HUMAN = "human"
    AI = "ai"


class RoutingType:
    DIRECT = "direct"
    BROADCAST = "broadcast"


class PlaybookExecutionType(str, Enum):
    INT = "INT"
    EXT = "EXT"

    @classmethod
    def __getitem__(cls, key):
        return cls(key.upper())
