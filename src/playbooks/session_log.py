import textwrap
from abc import ABC
from typing import Iterator, List


class SessionLogItem(ABC):
    def shorten(
        self, message: str, max_length: int = 100, placeholder: str = "..."
    ) -> str:
        if len(message) <= max_length:
            return message
        message = textwrap.shorten(message, max_length, placeholder=placeholder)
        if len(message) < 10 + len(placeholder):
            return ""
        else:
            return message


class SessionLogItemMessage(SessionLogItem):
    def __init__(self, message: str):
        self.message = message

    def __repr__(self) -> str:
        return self.message

    def to_log_full(self) -> str:
        return self.message


class SessionLog:
    def __init__(self, klass: str, agent_id: str):
        self.klass = klass
        self.agent_id = agent_id
        self.log: List[dict] = []

    def add(
        self,
        item: SessionLogItem,
    ):
        self.append(item)

    def __getitem__(self, index):
        return self.log[index]["item"]

    def __iter__(self) -> Iterator[SessionLogItem]:
        return iter(self.log)

    def __len__(self) -> int:
        return len(self.log)

    def __repr__(self) -> str:
        return repr(self.log)

    def append(
        self,
        item: SessionLogItem | str,
    ):
        if isinstance(item, str):
            if not item.strip():
                return
            item = SessionLogItemMessage(item)
        self.log.append({"item": item})

    def __str__(self) -> str:
        parts = []
        for item in self.log:
            message = item["item"].to_log_full()
            if message:
                parts.append(message)
        return "\n".join(parts)

    def to_log_full(self) -> str:
        parts = []
        for item in self.log:
            message = item["item"].to_log_full()
            if message:
                parts.append(message)
        return "\n".join(parts)
