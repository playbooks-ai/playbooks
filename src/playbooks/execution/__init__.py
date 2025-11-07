"""LLM execution strategies for playbooks.

This module provides different strategies for executing LLM-based playbooks,
including raw LLM calls, structured playbook execution, and ReAct-style
reasoning and action patterns.
"""

# Note: Imports removed to avoid circular dependencies.
# Import directly from submodules:
#   from playbooks.execution.base import LLMExecution
#   from playbooks.execution.playbook import PlaybookLLMExecution
#   from playbooks.execution.raw import RawLLMExecution
#   from playbooks.execution.react import ReActLLMExecution

__all__ = [
    "LLMExecution",
    "PlaybookLLMExecution",
    "ReActLLMExecution",
    "RawLLMExecution",
]
