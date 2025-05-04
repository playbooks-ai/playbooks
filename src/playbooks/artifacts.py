from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Artifact:
    """An artifact."""

    name: str
    summary: str
    content: Any

    def __repr__(self) -> str:
        return f"Artifact(name={self.name}, summary={self.summary})"

    def __str__(self) -> str:
        return self.__repr__()


class Artifacts:
    """A collection of artifacts."""

    def __init__(self):
        """Initialize a collection of artifacts."""
        self.artifacts: Dict[str, Artifact] = {}

    def set(self, name: str, summary: str, content: Any):
        """Set an artifact."""
        self.artifacts[name] = Artifact(name, summary, content)

    def to_dict(self) -> Dict[str, str]:
        """Return a dictionary representation of the artifacts."""
        return {artifact.name: artifact.summary for artifact in self.artifacts.values()}

    # Act as a dict
    def __getitem__(self, key: str) -> Artifact:
        return self.artifacts[key]

    def __setitem__(self, key: str, value: Artifact):
        self.artifacts[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self.artifacts

    def __iter__(self):
        return iter(self.artifacts.values())

    def __len__(self) -> int:
        return len(self.artifacts)

    def __repr__(self) -> str:
        return f"Artifacts({self.artifacts})"

    def __str__(self) -> str:
        return f"Artifacts({self.artifacts})"
