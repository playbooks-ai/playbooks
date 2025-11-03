"""Variable management system for playbook execution.

This module provides the variable system that tracks variable values,
changes, and history during playbook execution, with support for artifacts
and reactive updates.
"""

import types
from typing import Any, Dict, List, Optional, Union

from .call_stack import InstructionPointer
from .event_bus import EventBus
from .events import VariableUpdateEvent


class VariableChangeHistoryEntry:
    """Represents a single change in a variable's value history."""

    def __init__(self, instruction_pointer: InstructionPointer, value: Any) -> None:
        """Initialize a variable change history entry.

        Args:
            instruction_pointer: Location where the change occurred
            value: The new value after this change
        """
        self.instruction_pointer = instruction_pointer
        self.value = value


class Variable:
    """Represents a variable with change tracking.

    Tracks the current value and history of all changes to the variable
    throughout playbook execution.
    """

    def __init__(self, name: str, value: Any) -> None:
        """Initialize a variable.

        Args:
            name: Variable name (typically with $ prefix)
            value: Initial value
        """
        self.name = name
        self.value = value
        self.change_history: List[VariableChangeHistoryEntry] = []

    def update(
        self, new_value: Any, instruction_pointer: Optional[InstructionPointer] = None
    ) -> None:
        """Update the variable value and record the change.

        Args:
            new_value: The new value to assign
            instruction_pointer: Location where this update occurred
        """
        self.change_history.append(
            VariableChangeHistoryEntry(instruction_pointer, new_value)
        )
        self.value = new_value

    def __repr__(self) -> str:
        """Return string representation of the variable."""
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
    ) -> None:
        """Update the artifact value and summary.

        Args:
            new_value: Must be an Artifact object
            instruction_pointer: Location where this update occurred

        Raises:
            ValueError: If new_value is not an Artifact object
        """
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

    def __getitem__(self, key: Union[int, slice]) -> str:
        """Support artifact[0] and artifact[0:5] (indexing/slicing)."""
        return str(self.value)[key]

    def __contains__(self, item: Any) -> bool:
        """Support "substring" in artifact."""
        return str(item) in str(self.value)

    def __eq__(self, other: Any) -> bool:
        """Support artifact == "string"."""
        if isinstance(other, Artifact):
            return self.value == other.value
        return str(self.value) == str(other)

    def __lt__(self, other: Any) -> bool:
        """Support artifact < "string"."""
        if isinstance(other, Artifact):
            return str(self.value) < str(other.value)
        return str(self.value) < str(other)

    def __le__(self, other: Any) -> bool:
        """Support artifact <= "string"."""
        if isinstance(other, Artifact):
            return str(self.value) <= str(other.value)
        return str(self.value) <= str(other)

    def __gt__(self, other: Any) -> bool:
        """Support artifact > "string"."""
        if isinstance(other, Artifact):
            return str(self.value) > str(other.value)
        return str(self.value) > str(other)

    def __ge__(self, other: Any) -> bool:
        """Support artifact >= "string"."""
        if isinstance(other, Artifact):
            return str(self.value) >= str(other.value)
        return str(self.value) >= str(other)


class Variables:
    """A collection of variables with change history."""

    def __init__(self, event_bus: EventBus, agent_id: str = "unknown") -> None:
        """Initialize a Variables collection.

        Args:
            event_bus: Event bus for publishing variable update events
            agent_id: ID of the agent owning these variables
        """
        self.variables: Dict[str, Variable] = {}
        self.event_bus = event_bus
        self.agent_id = agent_id

    def update(self, vars: Union["Variables", Dict[str, Any]]) -> None:
        """Update multiple variables at once.

        Args:
            vars: Either a Variables instance or a dict of name->value mappings
        """
        if isinstance(vars, Variables):
            for name, value in vars.variables.items():
                self[name] = value.value
        else:
            for name, value in vars.items():
                self[name] = value

    def __getitem__(self, name: str) -> Variable:
        """Get a variable by name.

        Args:
            name: Variable name (with or without $ prefix)

        Returns:
            Variable object

        Raises:
            KeyError: If variable doesn't exist
        """
        return self.variables[name]

    def __setitem__(
        self,
        name: str,
        value: Any,
        instruction_pointer: Optional[InstructionPointer] = None,
    ) -> None:
        """Set or update a variable value.

        Automatically creates Variable or Artifact objects as needed.
        Publishes VariableUpdateEvent to the event bus.

        Args:
            name: Variable name (with or without $ prefix)
            value: Value to assign (can be Variable, Artifact, or any value)
            instruction_pointer: Location where this assignment occurred
        """
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
        """Check if a variable exists.

        Args:
            name: Variable name to check

        Returns:
            True if variable exists, False otherwise
        """
        return name in self.variables

    def __iter__(self) -> Any:
        """Iterate over all variables."""
        return iter(self.variables.values())

    def __len__(self) -> int:
        """Return the number of variables."""
        return len(self.variables)

    def public_variables(self) -> Dict[str, Variable]:
        """Get all public variables (excluding private variables starting with $_).

        Returns:
            Dictionary of public variable names to Variable objects
        """
        return {
            name: variable
            for name, variable in self.variables.items()
            if not name.startswith("$_")
        }

    def to_dict(self, include_private: bool = False) -> Dict[str, Any]:
        """Convert variables to a dictionary representation.

        Args:
            include_private: If True, include variables starting with $_ or _

        Returns:
            Dictionary mapping variable names to their values (or artifact summaries)
        """
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
