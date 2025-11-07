"""Playbook implementations for different execution modes.

This module provides various playbook types that define how agents execute
tasks, including LLM-based playbooks, Python function playbooks, local execution,
and remote server execution.
"""

from playbooks.triggers import PlaybookTrigger, PlaybookTriggers
from .base import Playbook
from .local import LocalPlaybook
from .llm_playbook import LLMPlaybook
from .python_playbook import PythonPlaybook
from .remote import RemotePlaybook

__all__ = [
    "Playbook",
    "LocalPlaybook",
    "LLMPlaybook",
    "PythonPlaybook",
    "RemotePlaybook",
    "PlaybookTrigger",
    "PlaybookTriggers",
]
