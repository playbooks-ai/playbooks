"""State management for playbook execution.

Import directly from submodules to avoid circular dependencies:
    from playbooks.state.execution_state import ExecutionState
    from playbooks.state.variables import Variables, Artifact
    from playbooks.state.call_stack import CallStack, InstructionPointer
etc.
"""

# Note: Imports intentionally minimal to avoid circular dependencies
# Import directly from submodules as needed

__all__ = []
