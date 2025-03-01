from typing import List, Union


class TraceItem:
    def __init__(self, item: Union["TraceMixin", str], metadata: dict = None):
        self.item = item
        self.metadata = metadata

    def __repr__(self):
        return self.item.__repr__()

    def __str__(self):
        return self.item.__str__()


class TraceMixin:
    def __init__(self):
        self._trace_items: List[TraceItem] = []
        self._trace_summary: str = "Empty"

    def trace(self, item: Union["TraceMixin", str], metadata: dict = None):
        self._trace_items.append(TraceItem(item, metadata))
        self.refresh_trace_summary()

    def refresh_trace_summary(self):
        self._trace_summary = self.to_trace()

    def __str__(self):
        return self._trace_summary

    def to_trace(self, depth: int = 1) -> str:
        if depth <= 0:
            return self._trace_summary

        trace = []
        for item in self._trace_items:
            if isinstance(item.item, TraceMixin):
                lines = item.item.__repr__().split("\n")
                trace.append(f"{depth * '  '}- {lines[0]}")
                if len(lines) > 1:
                    for line in lines[1:]:
                        trace.append(f"{depth * '  '}  {line}")
                trace.append(item.item.to_trace(depth + 1))
            else:
                if item.item:
                    trace.append(f"{depth * '  '}- {item.item}")
        return "\n".join(trace)


class TraceWalker:
    @staticmethod
    def walk(trace_item: Union[TraceMixin, TraceItem], visitor_fn):
        """Performs a depth-first walk of trace items and calls the visitor function on each item.

        Args:
            trace_item: The trace item or TraceMixin instance to walk
            visitor_fn: Lambda function to call on each item. Should accept a TraceItem as argument.
        """
        if isinstance(trace_item, TraceMixin):
            for item in trace_item._trace_items:
                TraceWalker.walk(item, visitor_fn)
        elif isinstance(trace_item, TraceItem):
            visitor_fn(trace_item)
            if isinstance(trace_item.item, TraceMixin):
                TraceWalker.walk(trace_item.item, visitor_fn)
