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

    def to_dict(self) -> Dict[str, Any]:
        return {
            name: variable.value
            for name, variable in self.variables.items()
            if variable.value is not None and not variable.name.startswith("$_")
        }

    def __repr__(self) -> str:
        return f"Variables({self.to_dict()})"
