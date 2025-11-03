"""Agent classes for the playbooks framework.

This package provides various agent implementations including AI agents,
human agents, and specialized agent types for different communication
protocols and execution modes.
"""

from .ai_agent import AIAgent
from .base_agent import BaseAgent
from .human_agent import HumanAgent
from .local_ai_agent import LocalAIAgent
from .mcp_agent import MCPAgent
from .remote_ai_agent import RemoteAIAgent

__all__ = [
    "BaseAgent",
    "HumanAgent",
    "AIAgent",
    "LocalAIAgent",
    "RemoteAIAgent",
    "MCPAgent",
]
