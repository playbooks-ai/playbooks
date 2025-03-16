import uuid
from typing import List, Union

from .types import AgentResponseChunk


def indent(string: str, level: int) -> str:
    return "\n".join(f"{'  ' * level}{line}" for line in string.split("\n"))


class TraceMixin:
    def __init__(self):
        self._trace_id = str(uuid.uuid4())
        self._trace_metadata = {}
        self._trace_items: List[TraceMixin] = []

    def trace(self, item: Union["TraceMixin", str], metadata: dict = None):
        if isinstance(item, str):
            item = StringTrace(item)

        item._trace_metadata["parent_id"] = self._trace_id

        # Add any additional metadata
        if metadata:
            item._trace_metadata.update(metadata)

        self._trace_items.append(item)

    def to_trace(self) -> Union[str, List]:
        return [item.to_trace() for item in self._trace_items]

    def yield_trace(self):
        yield AgentResponseChunk(trace=self.to_trace())


class StringTrace(TraceMixin):
    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def to_trace(self) -> Union[str, List]:
        return self.message


class TraceWalker:
    @staticmethod
    def walk(trace_item: TraceMixin, visitor_fn):
        """Performs a depth-first walk of trace items and calls the visitor function on each item.

        Args:
            trace_item: The trace item or TraceMixin instance to walk
            visitor_fn: Lambda function to call on each item. Should accept a TraceMixin as argument.
        """
        if isinstance(trace_item, TraceMixin):
            for item in trace_item._trace_items:
                visitor_fn(item)
                TraceWalker.walk(item, visitor_fn)
