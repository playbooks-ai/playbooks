import textwrap
from typing import Any

from playbooks.session_log import SessionLogItem


class PlaybookCall(SessionLogItem):
    def __init__(self, playbook_klass: str, args, kwargs):
        self.playbook_klass = playbook_klass
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        code = []
        code.append(self.playbook_klass)
        code.append("(")
        if self.args:
            code.append(", ".join([str(a) for a in self.args]))
        if self.kwargs:
            code.append(", ".join(f"{k}={v}" for k, v in self.kwargs.items()))
        code.append(")")
        code = "".join(code)

        return code

    def to_log_full(self) -> str:
        if self.playbook_klass == "Say" or self.playbook_klass == "SaveArtifact":
            return ""
        return str(self)

    def to_log_compact(self) -> str:
        return textwrap.shorten(str(self), 30, placeholder="...")

    def to_log_minimal(self) -> str:
        return self.playbook_klass + "()"


class PlaybookCallResult(SessionLogItem):
    def __init__(self, call: PlaybookCall, result: Any):
        self.call = call
        self.result = result

    def __str__(self):
        return self.to_log(str(self.result))

    def to_log(self, result_str: str) -> str:
        if (
            self.call.playbook_klass == "Say"
            or self.call.playbook_klass == "SaveArtifact"
        ):
            return ""
        if self.result is None:
            return f"{self.call.to_log_minimal()} finished"
        return f"{self.call.to_log_minimal()} returned {result_str}"

    def to_log_full(self) -> str:
        return self.to_log(str(self.result) if self.result else "")

    def to_log_compact(self) -> str:
        return self.to_log(
            textwrap.shorten(str(self.result), 20, placeholder="...")
            if self.result
            else ""
        )

    def to_log_minimal(self) -> str:
        return self.to_log("success")
