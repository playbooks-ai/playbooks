from typing import Dict, List

from .call_stack import InstructionPointer


class VariableChangeHistoryEntry:
    def __init__(self, instruction_pointer: InstructionPointer, value: any):
        self.instruction_pointer = instruction_pointer
        self.value = value


class Variable:
    def __init__(self, name: str, value: any):
        self.name = name
        self.value = value
        self.change_history: List[VariableChangeHistoryEntry] = []

    def update(self, new_value: any, instruction_pointer: InstructionPointer):
        self.change_history.append(
            VariableChangeHistoryEntry(instruction_pointer, new_value)
        )
        self.value = new_value

    def __repr__(self) -> str:
        return f"{self.name}={self.value}"


class Variables:
    def __init__(self):
        self.variables: Dict[str, Variable] = {}

    def update(self, vars: Dict[str, any]):
        for name, value in vars.items():
            self[name] = value

    def __getitem__(self, name: str) -> Variable:
        return self.variables.get(name, None)

    def __setitem__(
        self,
        name: str,
        value: any,
        instruction_pointer: InstructionPointer = None,
    ):
        if ":" in name:
            name = name.split(":")[0]
        if name not in self.variables:
            self.variables[name] = Variable(name, value)
        self.variables[name].update(value, instruction_pointer)

    def __contains__(self, name: str) -> bool:
        return name in self.variables

    def __iter__(self):
        return iter(self.variables.values())

    def __len__(self):
        return len(self.variables)

    def to_dict(self):
        return {name: variable.value for name, variable in self.variables.items()}

    def __repr__(self) -> str:
        return f"Variables({self.to_dict()})"
