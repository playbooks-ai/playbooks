import textwrap
from typing import Any

from playbooks.session_log import SessionLogItem
from playbooks.utils.text_utils import simple_shorten
from playbooks.variables import Artifact


class PlaybookCall(SessionLogItem):
    def __init__(
        self,
        playbook_klass: str,
        args,
        kwargs,
        variable_to_assign: str = None,
        type_annotation: str = None,
    ):
        self.playbook_klass = playbook_klass
        self.args = args
        self.kwargs = kwargs
        self.variable_to_assign = variable_to_assign  # e.g., "$result"
        self.type_annotation = type_annotation  # e.g., "bool"

    def __str__(self):
        from playbooks.argument_types import LiteralValue, VariableReference
        from playbooks.variables import Artifact

        code = [self.playbook_klass, "("]

        # Format args
        if self.args:
            formatted_args = []
            for arg in self.args:
                if isinstance(arg, VariableReference):
                    formatted_args.append(arg.reference)  # Show "$var"
                elif isinstance(arg, LiteralValue):
                    formatted_args.append(repr(arg.value))
                elif isinstance(arg, Artifact):
                    formatted_args.append(f"${arg.name}")  # Show reference
                else:
                    formatted_args.append(str(arg))
            code.append(", ".join(formatted_args))

        # Format kwargs
        if self.kwargs:
            if self.args:
                code.append(", ")
            formatted_kwargs = []
            for k, v in self.kwargs.items():
                if isinstance(v, VariableReference):
                    formatted_kwargs.append(f"{k}={v.reference}")
                elif isinstance(v, LiteralValue):
                    formatted_kwargs.append(f"{k}={repr(v.value)}")
                elif isinstance(v, Artifact):
                    formatted_kwargs.append(f"{k}=${v.name}")
                else:
                    formatted_kwargs.append(f"{k}={v}")
            code.append(", ".join(formatted_kwargs))

        code.append(")")
        return "".join(code)

    def to_log_full(self) -> str:
        if self.playbook_klass == "Say" or self.playbook_klass == "SaveArtifact":
            return self.to_log_minimal()
        return str(self)

    def to_log_compact(self) -> str:
        return simple_shorten(str(self), 30, placeholder="...")

    def to_log_minimal(self) -> str:
        return self.playbook_klass + "()"


class PlaybookCallResult(SessionLogItem):
    def __init__(self, call: PlaybookCall, result: Any, execution_summary: str = None):
        self.call = call
        self.result = result
        self.execution_summary = execution_summary

    def __str__(self):
        return self.to_log(str(self.result))

    def to_log(self, result_str: str) -> str:
        if (
            self.call.playbook_klass == "Say"
            or self.call.playbook_klass == "SaveArtifact"
        ):
            return ""

        output = []
        if self.execution_summary:
            output.append(self.execution_summary)

        if self.result is None:
            output.append(f"{self.call.to_log_full()} finished")
        else:
            output.append(f"{self.call.to_log_full()} → {result_str}")

        return "\n".join(output)

    def to_log_full(self) -> str:
        # if result is a list, join str() of items with newlines
        result_str = None
        if isinstance(self.result, list):
            result_str = "\n".join([str(item) for item in self.result])
        elif isinstance(self.result, Artifact):
            result_str = (
                f'Artifact ${self.result.name} with summary "{self.result.summary}"'
            )
        else:
            result_str = str(self.result)
        return self.to_log(result_str if result_str else "")

    def to_log_compact(self) -> str:
        return self.to_log(
            textwrap.shorten(str(self.result), 20, placeholder="...")
            if self.result
            else ""
        )

    def to_log_minimal(self) -> str:
        return self.to_log("success")
