import os
from dataclasses import dataclass
from typing import AsyncIterator, List, Optional, Union

from litellm import acompletion
from md2py import md2py

from playbooks.config import DEFAULT_MODEL

from .loader import load


class PlaybooksAgent:
    # static method factory that takes in playbooks ast and creates a PlaybooksAgent for
    # each H1 header
    @staticmethod
    def from_ast(ast):
        # Use visitor pattern to find all H1 headers
        # Create an agent for each H1 header
        return [PlaybooksAgent(str(h1)) for h1 in ast.h1s]

    def __init__(self, name: str):
        self.name = name


@dataclass
class RuntimeConfig:
    model: str = None
    api_key: Optional[str] = None

    def __post_init__(self):
        self.model = self.model or os.environ.get("MODEL") or DEFAULT_MODEL
        self.api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")


class PlaybooksRuntime:
    def __init__(self, config: RuntimeConfig = None):
        self.config = config or RuntimeConfig()
        # Markdown content of all playbooks
        self.playbooks_content: str = None

        # Abstract syntax tree of all playbooks
        self.ast: dict = None

        # List of agents
        self.agents: List[PlaybooksAgent] = []

        # List of events
        self.events: List[dict] = []

    def load(self, playbook_path: str) -> None:
        # Load playbook content using the loader
        self.playbooks_content = load([playbook_path])
        self.events.append({"type": "load", "playbooks": self.playbooks_content})

        self.ast = md2py(self.playbooks_content)
        self.events.append(
            {
                "type": "parse_to_ast",
                "playbooks": self.playbooks_content,
                "ast": self.ast,
            }
        )

        self.agents = PlaybooksAgent.from_ast(self.ast)

    async def run(self, playbooks: str, stream: bool = False, **kwargs) -> Union[str, AsyncIterator[str]]:
        """Run playbooks using the configured model"""
        self.events.append({"type": "user_message", "message": ""})
        if stream:
            return self.stream(playbooks, **kwargs)

        raw_response = await acompletion(
            model=self.config.model,
            messages=[{"role": "user", "content": playbooks}],
            api_key=self.config.api_key,
            **kwargs
        )
        response = raw_response.choices[0].message.content
        self.events.append({"type": "agent_message", "message": response})
        return response

    async def stream(self, playbooks: str, **kwargs) -> AsyncIterator[str]:
        """Run playbooks using the configured model with streaming enabled"""
        response = await acompletion(
            model=self.config.model,
            messages=[{"role": "user", "content": playbooks}],
            api_key=self.config.api_key,
            stream=True,
            **kwargs
        )
        complete_message = ""
        async for chunk in response:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                complete_message += content
                yield content

        # log event after streaming is complete with accumulated message
        self.events.append({"type": "agent_message", "message": complete_message})


class SingleThreadedPlaybooksRuntime(PlaybooksRuntime):
    async def run(self, playbooks: str = None, **kwargs) -> str:
        """Run playbooks."""
        return await super().run(playbooks or self.playbooks_content, **kwargs)


async def run(playbooks: str, **kwargs) -> str:
    """Convenience function to run playbooks"""
    model = kwargs.pop("model", None)
    api_key = kwargs.pop("api_key", None)
    config = RuntimeConfig(model=model, api_key=api_key)
    runtime = SingleThreadedPlaybooksRuntime(config)
    return await runtime.run(playbooks, **kwargs)
