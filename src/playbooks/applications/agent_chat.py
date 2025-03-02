import logging
from dataclasses import dataclass
from typing import Iterable, List, Optional

import typer
from rich.console import Console
from rich.prompt import Prompt

from playbooks.agent_factory import AgentFactory
from playbooks.config import LLMConfig
from playbooks.exceptions import AgentConfigurationError
from playbooks.human_agent import HumanAgent
from playbooks.message_router import MessageRouter
from playbooks.types import AgentResponseChunk

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = typer.Typer()
console = Console()


@dataclass
class AgentChatConfig:
    playbooks_paths: List[str] = None
    playbooks_content: Optional[str] = None
    main_model_config: LLMConfig = None


class AgentChat:
    def __init__(self, config: AgentChatConfig = None):
        self.config = config or AgentChatConfig()

        if config:
            if config.playbooks_paths:
                self.agents = AgentFactory.from_playbooks_paths(
                    config.playbooks_paths, config.main_model_config
                )
            elif config.playbooks_content:
                self.agents = AgentFactory.from_playbooks_content(
                    config.playbooks_content, config.main_model_config
                )
            else:
                raise AgentConfigurationError(
                    "Expected either playbooks_paths or playbooks_content to be set"
                )

        if len(self.agents) != 1:
            raise AgentConfigurationError(
                f"Expected 1 agent, but found {len(self.agents)}"
            )

        self.ai_agent_class = self.agents[list(self.agents.keys())[0]]
        self.ai_agent = self.ai_agent_class()
        self.human_agent = self.agents["User"] = HumanAgent(klass="User")

    def run(self, stream: bool):
        """Run the agent and return chunks.

        Args:
            stream: Whether to stream the response chunks or collect them all.

        Returns:
            An iterable of AgentResponseChunk objects. When stream=True, yields chunks
            one by one as they're generated. When stream=False, collects all chunks
            and then yields them.
        """
        chunks = []
        for chunk in self.ai_agent.run(
            llm_config=self.config.main_model_config, stream=stream
        ):
            if stream:
                yield chunk
            else:
                chunks.append(chunk)

        if not stream:
            yield from chunks

    def process_user_message(self, message: str, stream: bool):
        """Process a user message and return response chunks.

        Args:
            message: The user message to process.
            stream: Whether to stream the response chunks or collect them all.

        Returns:
            An iterable of AgentResponseChunk objects. The behavior depends on the
            MessageRouter implementation, but generally follows the stream parameter.
        """
        return MessageRouter.send_message(
            message=message,
            from_agent=self.human_agent,
            to_agent=self.ai_agent,
            llm_config=self.config.main_model_config,
            stream=stream,
        )


@app.command()
def main(
    playbooks_paths: List[str] = typer.Argument(  # noqa: B008
        ..., help="One or more paths to playbook files. Supports glob patterns"
    ),
    model: str = typer.Option(None, help="Model name for the selected LLM"),
    api_key: Optional[str] = typer.Option(None, help="API key for the selected LLM"),
    stream: bool = typer.Option(False, help="Enable streaming output from LLM"),
):
    """Start an interactive chat session using the specified playbooks and LLM"""
    _chat(playbooks_paths=playbooks_paths, model=model, api_key=api_key, stream=stream)


def output(stream: bool, response_generator: Iterable[AgentResponseChunk]):
    if stream:
        agent_responses = []
        tool_responses = []
        for chunk in response_generator:
            if chunk:
                if chunk.raw:
                    console.print("[green]" + chunk.raw + "[/green]", end="")
                if chunk.trace:
                    console.print("[yellow]" + chunk.trace + "[/yellow]")
                if chunk.agent_response:
                    agent_responses.append(chunk.agent_response)
                if chunk.tool_response:
                    tool_responses.append(chunk.tool_response)

        # if tool_responses:
        #     for tool_response in tool_responses:
        #         console.print(
        #             "Tool: "
        #             + tool_response.code
        #             + " returned "
        #             + str(tool_response.output)
        #         )
        if agent_responses:
            for agent_response in agent_responses:
                console.print("[blue]Agent: " + agent_response + "[/blue]")
    else:
        chunks = list(response_generator)
        console.print("".join(chunk.raw for chunk in chunks if chunk.raw))
        console.print()
        agent_responses = []
        tool_responses = []
        for chunk in chunks:
            if chunk.agent_response:
                agent_responses.append(chunk.agent_response)
            if chunk.tool_response:
                tool_responses.append(chunk.tool_response)
        for tool_response in tool_responses:
            print(
                "Tool: " + tool_response.code + " returned " + str(tool_response.output)
            )
        for agent_response in agent_responses:
            print("Agent: " + agent_response)


def _chat(
    playbooks_paths: List[str],
    model: Optional[str],
    api_key: Optional[str],
    stream: bool,
):
    """Run the chat session"""
    config = AgentChatConfig(
        playbooks_paths=playbooks_paths,
        main_model_config=LLMConfig(model=model, api_key=api_key),
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

        # Print initial response from AI agent
        output(stream=stream, response_generator=agent_chat.run(stream=stream))

        # Start interactive chat loop
        while True:
            try:
                # Get user input
                user_message = Prompt.ask("\n[blue]User[/blue]")
                if not user_message:
                    continue

                # Process user message
                output(
                    stream=stream,
                    response_generator=agent_chat.process_user_message(
                        user_message, stream=stream
                    ),
                )

            except (KeyboardInterrupt, EOFError):
                break
            except Exception as e:
                # show error message and stack trace
                console.print(f"\n[red]Error: {str(e)}[/red]")
                raise e
                break

        console.print("\n[yellow]Goodbye![/yellow]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
    except Exception as e:
        console.print(f"\n[red]Fatal error:[/red] {str(e)}")
        raise


if __name__ == "__main__":
    app()
