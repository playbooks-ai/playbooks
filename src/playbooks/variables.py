import types
from typing import Any, Dict, List, Optional, Union

from .call_stack import InstructionPointer
from .event_bus import EventBus
from .events import VariableUpdateEvent


class VariableChangeHistoryEntry:
    def __init__(self, instruction_pointer: InstructionPointer, value: Any):
        self.instruction_pointer = instruction_pointer
        self.value = value


class Variable:
    def __init__(self, name: str, value: Any):
        self.name = name
        self.value = value
        self.change_history: List[VariableChangeHistoryEntry] = []

    def update(
        self, new_value: Any, instruction_pointer: Optional[InstructionPointer] = None
    ):
        self.change_history.append(
            VariableChangeHistoryEntry(instruction_pointer, new_value)
        )
        self.value = new_value

    def __repr__(self) -> str:
        return f"{self.name}={self.value}"


class Artifact(Variable):
    """An artifact - a Variable with additional summary metadata."""

    def __init__(self, name: str, summary: str, value: Any):
        """Initialize an Artifact.

        Args:
            name: Variable name (without $ prefix)
            summary: Short summary of the artifact
            value: The actual content/value
        """
        super().__init__(name, value)
        self.summary = summary

    def update(
        self, new_value: Any, instruction_pointer: Optional[InstructionPointer] = None
    ):
        self.change_history.append(
            VariableChangeHistoryEntry(instruction_pointer, new_value)
        )
        if isinstance(new_value, Artifact):
            self.summary = new_value.summary
            self.value = new_value.value
        else:
            raise ValueError("Artifact must be updated using an Artifact object")

    def __repr__(self) -> str:
        return f"Artifact(name={self.name}, summary={self.summary})"

    def __str__(self) -> str:
        return str(self.value)

    # String operation support - delegate to string representation of value
    def __len__(self) -> int:
        """Support len(artifact)."""
        return len(str(self.value))

    def __add__(self, other):
        """Support artifact + "text"."""
        return str(self.value) + str(other)

    def __radd__(self, other):
        """Support "text" + artifact."""
        return str(other) + str(self.value)

    def __mul__(self, n):
        """Support artifact * 3."""
        return str(self.value) * n

    def __rmul__(self, n):
        """Support 3 * artifact."""
        return n * str(self.value)

    def __getitem__(self, key):
        """Support artifact[0] and artifact[0:5] (indexing/slicing)."""
        return str(self.value)[key]

    def __contains__(self, item):
        """Support "substring" in artifact."""
        return str(item) in str(self.value)

    def __eq__(self, other):
        """Support artifact == "string"."""
        if isinstance(other, Artifact):
            return self.value == other.value
        return str(self.value) == str(other)

    def __lt__(self, other):
        """Support artifact < "string"."""
        if isinstance(other, Artifact):
            return str(self.value) < str(other.value)
        return str(self.value) < str(other)

    def __le__(self, other):
        """Support artifact <= "string"."""
        if isinstance(other, Artifact):
            return str(self.value) <= str(other.value)
        return str(self.value) <= str(other)

    def __gt__(self, other):
        """Support artifact > "string"."""
        if isinstance(other, Artifact):
            return str(self.value) > str(other.value)
        return str(self.value) > str(other)

    def __ge__(self, other):
        """Support artifact >= "string"."""
        if isinstance(other, Artifact):
            return str(self.value) >= str(other.value)
        return str(self.value) >= str(other)


class Variables:
    """A collection of variables with change history."""

    def __init__(self, event_bus: EventBus, agent_id: str = "unknown"):
        self.variables: Dict[str, Variable] = {}
        self.event_bus = event_bus
        self.agent_id = agent_id

    def update(self, vars: Union["Variables", Dict[str, Any]]) -> None:
        """Update multiple variables at once."""
        if isinstance(vars, Variables):
            for name, value in vars.variables.items():
                self[name] = value.value
        else:
            for name, value in vars.items():
                self[name] = value

    def __getitem__(self, name: str) -> Variable:
        return self.variables[name]

    def __setitem__(
        self,
        name: str,
        value: Any,
        instruction_pointer: Optional[InstructionPointer] = None,
    ) -> None:
        if ":" in name:
            name = name.split(":")[0]
        if isinstance(value, Artifact):
            if name not in self.variables:
                if name == value.name:
                    self.variables[name] = value
                else:
                    self.variables[name] = Variable(name, value)

            self.variables[name].update(value, instruction_pointer)
        elif isinstance(value, Variable):
            value = value.value
            if name not in self.variables:
                self.variables[name] = Variable(name, value)
            self.variables[name].update(value, instruction_pointer)
        else:
            if name not in self.variables:
                self.variables[name] = Variable(name, value)
            self.variables[name].update(value, instruction_pointer)

        event = VariableUpdateEvent(
            agent_id=self.agent_id,
            session_id="",
            variable_name=name,
            variable_value=value,
        )
        self.event_bus.publish(event)

    def __contains__(self, name: str) -> bool:
        return name in self.variables

    def __iter__(self):
        return iter(self.variables.values())

    def __len__(self) -> int:
        return len(self.variables)

    def public_variables(self) -> Dict[str, Variable]:
        """
        Returns:
            Dictionary of public variables (names not starting with $_)
        """
        return {
            name: variable
            for name, variable in self.variables.items()
            if not name.startswith("$_")
        }

    def to_dict(self, include_private: bool = False) -> Dict[str, Any]:

        result = {}
        for name, variable in self.variables.items():
            if variable.value is None:
                continue
            if not include_private and (
                variable.name.startswith("$_") or variable.name.startswith("_")
            ):
                continue

            # Skip non-serializable objects like modules and classes
            if isinstance(variable.value, (types.ModuleType, type)):
                continue

            # If value is an Artifact, use its string representation
            if isinstance(variable, Artifact):
                result[name] = "Artifact: " + variable.summary
            elif isinstance(variable.value, Artifact):
                result[name] = "Artifact: " + str(variable.value.summary)
            else:
                result[name] = variable.value

        return result

    def __repr__(self) -> str:
        return f"Variables({self.to_dict(include_private=True)})"
