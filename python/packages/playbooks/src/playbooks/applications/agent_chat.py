import asyncio
from dataclasses import dataclass
from typing import List, Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Prompt

from playbooks.cli.output import print_markdown, print_streaming_markdown
from playbooks.core.agents import AIAgent, HumanAgent
from playbooks.core.exceptions import RuntimeError
from playbooks.core.runtime import PlaybooksRuntime, RuntimeConfig

load_dotenv()

app = typer.Typer()
console = Console()


@dataclass
class AgentChatConfig:
    playbooks_paths: List[str]
    model: Optional[str] = None
    api_key: Optional[str] = None
    llm: Optional[str] = None

    def to_runtime_config(self) -> RuntimeConfig:
        return RuntimeConfig(model=self.model, api_key=self.api_key, llm_config=None)


class AgentChat:
    def __init__(self, config: AgentChatConfig = None):
        self.runtime = PlaybooksRuntime(
            config.to_runtime_config() if config else RuntimeConfig()
        )
        if config and config.playbooks_paths:
            self.runtime.load_from_paths(config.playbooks_paths)

        if len(self.runtime.agents) != 1:
            raise RuntimeError(
                f"Expected 1 agent, but found {len(self.runtime.agents)}"
            )

        self.runtime.agents.append(HumanAgent(klass="User"))

    @property
    def ai_agent(self):
        return self.runtime.agents[0]

    @property
    def human_agent(self):
        return self.runtime.agents[1]

    async def run(self):
        # Run each AI agent in the runtime
        # Only AI agents should be run
        for agent in self.runtime.agents:
            if isinstance(agent, AIAgent):
                async for chunk in agent.run(runtime=self.runtime):
                    yield chunk

    async def process_user_message(self, message: str):
        return self.runtime.router.send_message(
            message=message,
            from_agent=self.human_agent,
            to_agent=self.ai_agent,
        )


@app.command()
def main(
    playbooks_paths: List[str] = typer.Argument(  # noqa: B008
        ..., help="One or more paths to playbook files. Supports glob patterns"
    ),
    llm: str = typer.Option(
        None, help="LLM provider to use (openai, anthropic, vertexai)"
    ),
    model: str = typer.Option(None, help="Model name for the selected LLM"),
    api_key: Optional[str] = typer.Option(None, help="API key for the selected LLM"),
    stream: bool = typer.Option(True, help="Enable streaming output from LLM"),
):
    """Start an interactive chat session using the specified playbooks and LLM"""
    asyncio.run(_async_chat(playbooks_paths, llm, model, api_key, stream))


async def _async_chat(
    playbooks_paths: List[str],
    llm: Optional[str],
    model: Optional[str],
    api_key: Optional[str],
    stream: bool,
):
    """Run the async chat session"""
    config = AgentChatConfig(
        playbooks_paths=playbooks_paths,
        llm=llm,
        model=model,
        api_key=api_key,
    )
    agent_chat = AgentChat(config)

    try:
        console.print(f"\nLoading playbooks from: {playbooks_paths}")
        console.print("\nLoaded playbooks successfully")
        console.print(
            f"\nInitializing runtime with model={model}, "
            f"api_key={'*' * len(api_key) if api_key else None}"
        )
        console.print("\nRuntime initialized successfully")

        # Run application
        console.print("\n[yellow]Agent: [/yellow]")
        response = agent_chat.run()
        if stream:
            await print_streaming_markdown(response)
        else:
            print_markdown(response)

        while True:
            try:
                user_input = Prompt.ask("\n[blue]User[/blue]")
                if user_input.lower() in ["exit", "quit"]:
                    console.print("\nExiting chat loop...")
                    return

                console.print("\n[yellow]Agent: [/yellow]")
                response = await agent_chat.process_user_message(user_input)
                if stream:
                    await print_streaming_markdown(response)
                else:
                    print_markdown(response)

            except Exception as e:
                console.print(f"\n[red]Error in chat loop:[/red] {str(e)}")
                raise

    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
    except Exception as e:
        console.print(f"\n[red]Fatal error:[/red] {str(e)}")
        raise


if __name__ == "__main__":
    app()
