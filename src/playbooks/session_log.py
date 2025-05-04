import textwrap
from abc import ABC
from enum import Enum
from typing import Iterator, List


class SessionLogItemLevel(Enum):
    HIGH = 0
    MEDIUM = 1
    LOW = 2


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

    def to_log_compact(self) -> str:
        return self.shorten(self.message, 200, placeholder="...")

    def to_log_minimal(self) -> str:
        return self.shorten(self.message, 50, placeholder="...")


class SessionLog:
    def __init__(self):
        self.log: List[dict[SessionLogItemLevel, SessionLogItem]] = []

    def add(
        self,
        item: SessionLogItem,
        level: SessionLogItemLevel = SessionLogItemLevel.MEDIUM,
    ):
        self.append(item, level)

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
        level: SessionLogItemLevel = SessionLogItemLevel.MEDIUM,
    ):
        if isinstance(item, str):
            if not item.strip():
                return
            item = SessionLogItemMessage(item)
        self.log.append({"item": item, "level": level})

    def __str__(self) -> str:
        parts = []
        for index, item in enumerate(self.log):
            reverse_index = len(self.log) - index
            level = item["level"]

            if (
                (level == SessionLogItemLevel.HIGH and reverse_index < 30)
                or (level == SessionLogItemLevel.MEDIUM and reverse_index < 20)
                or (level == SessionLogItemLevel.LOW and reverse_index < 10)
            ):
                item_str = item["item"].to_log_full()

            elif (
                (level == SessionLogItemLevel.HIGH and reverse_index < 40)
                or (level == SessionLogItemLevel.MEDIUM and reverse_index < 30)
                or (level == SessionLogItemLevel.LOW and reverse_index < 20)
            ):
                item_str = item["item"].to_log_compact()

            elif (
                (level == SessionLogItemLevel.HIGH and reverse_index < 50)
                or (level == SessionLogItemLevel.MEDIUM and reverse_index < 40)
                or (level == SessionLogItemLevel.LOW and reverse_index < 30)
            ):
                item_str = item["item"].to_log_minimal()

            else:
                item_str = ""

            if item_str:
                parts.append(item_str)
        return "\n".join(parts)

    def to_log_full(self) -> str:
        parts = []
        for item in self.log:
            message = item["item"].to_log_full()
            if message:
                parts.append(message)
        return "\n".join(parts)
