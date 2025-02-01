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
from playbooks.utils.cli import print_markdown

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = typer.Typer()
console = Console()


@dataclass
class AgentChatConfig:
    playbooks_paths: List[str]
    main_model_config: LLMConfig = None


class AgentChat:
    def __init__(self, config: AgentChatConfig = None):
        self.config = config or AgentChatConfig()

        if config and config.playbooks_paths:
            self.agents = AgentFactory.from_playbooks_paths(
                config.playbooks_paths, config.main_model_config
            )

        if len(self.agents) != 1:
            raise AgentConfigurationError(
                f"Expected 1 agent, but found {len(self.agents)}"
            )

        self.ai_agent_class = self.agents[list(self.agents.keys())[0]]
        self.ai_agent = self.ai_agent_class()
        self.human_agent = self.agents["User"] = HumanAgent(klass="User")

    def run(self, stream: bool):
        """Run the agent and return both raw chunks and agent responses.

        Returns:
            AgentResponse: Object containing two independent streams:
                - raw_stream: yields raw LLM chunks
                - agent_response_stream: yields messages from Say() calls
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
        return MessageRouter.send_message(
            message=message,
            from_agent=self.human_agent,
            to_agent=self.ai_agent,
            llm_config=self.config.main_model_config,
            stream=stream,
        )


def _process_buffer(buffer: str) -> tuple[str, str]:
    """Process buffer and return tuple of (text_to_print, remaining_buffer).
    Handles both newlines and code blocks."""
    if "```" not in buffer:
        last_newline = buffer.rfind("\n")
        if last_newline != -1:
            return buffer[: last_newline + 1], buffer[last_newline + 1 :]
        return "", buffer

    # Find first ``` and check if we have a closing ```
    start = buffer.find("```")
    end = buffer.find("```", start + 3)
    if end == -1:
        # No closing ```, check if we can print anything before the opening ```
        last_newline = buffer[:start].rfind("\n")
        if last_newline != -1:
            return buffer[: last_newline + 1], buffer[last_newline + 1 :]
        return "", buffer

    # We have a complete code block, find the next newline after it
    next_newline = buffer[end + 3 :].find("\n")
    if next_newline != -1:
        print_until = end + 3 + next_newline + 1
        return buffer[:print_until], buffer[print_until:]

    return "", buffer


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
    stream: bool = typer.Option(False, help="Enable streaming output from LLM"),
):
    """Start an interactive chat session using the specified playbooks and LLM"""
    _chat(playbooks_paths=playbooks_paths, model=model, api_key=api_key, stream=stream)


def output(stream: bool, response_generator: Iterable[AgentResponseChunk]):
    if stream:
        buffer = ""
        agent_responses = []
        tool_responses = []
        for chunk in response_generator:
            if chunk:
                if chunk.raw:
                    buffer += chunk.raw
                    to_print, buffer = _process_buffer(buffer)
                    if to_print:
                        print_markdown(to_print)
                if chunk.agent_response:
                    agent_responses.append(chunk.agent_response)
                if chunk.tool_response:
                    tool_responses.append(chunk.tool_response)
        # Print any remaining content in the buffer
        if buffer:
            print_markdown(buffer)

        if tool_responses:
            for tool_response in tool_responses:
                print_markdown(
                    "Tool: "
                    + tool_response.code
                    + " returned "
                    + str(tool_response.output)
                )
        if agent_responses:
            for agent_response in agent_responses:
                print_markdown("Agent: " + agent_response)
    else:
        chunks = list(response_generator)
        print_markdown("".join(chunk.raw for chunk in chunks if chunk.raw))
        print()
        agent_responses = []
        tool_responses = []
        for chunk in chunks:
            if chunk.agent_response:
                agent_responses.append(chunk.agent_response)
            if chunk.tool_response:
                tool_responses.append(chunk.tool_response)
        for tool_response in tool_responses:
            print_markdown(
                "Tool: " + tool_response.code + " returned " + str(tool_response.output)
            )
        for agent_response in agent_responses:
            print_markdown("Agent: " + agent_response)


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
