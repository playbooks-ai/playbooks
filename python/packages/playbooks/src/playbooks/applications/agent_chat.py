import logging
from dataclasses import dataclass
from typing import List, Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Prompt

from playbooks.cli.output import print_markdown
from playbooks.core.agents import AIAgent, HumanAgent
from playbooks.core.exceptions import RuntimeError
from playbooks.core.runtime import PlaybooksRuntime, RuntimeConfig

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

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

    def run(self):
        # Run each AI agent in the runtime
        # Only AI agents should be run
        for agent in self.runtime.agents:
            if isinstance(agent, AIAgent):
                for chunk in agent.run(runtime=self.runtime):
                    yield chunk

    def process_user_message(self, message: str):
        return self.runtime.router.send_message(
            message=message,
            from_agent=self.human_agent,
            to_agent=self.ai_agent,
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
    stream: bool = typer.Option(True, help="Enable streaming output from LLM"),
):
    """Start an interactive chat session using the specified playbooks and LLM"""
    _chat(playbooks_paths, llm, model, api_key, stream)


def _chat(
    playbooks_paths: List[str],
    llm: Optional[str],
    model: Optional[str],
    api_key: Optional[str],
    stream: bool,
):
    """Run the chat session"""
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

        # Print initial response from AI agent
        if stream:
            buffer = ""
            for chunk in agent_chat.run():
                buffer += chunk
                to_print, buffer = _process_buffer(buffer)
                if to_print:
                    print_markdown(to_print)
            # Print any remaining content in the buffer
            if buffer:
                print_markdown(buffer)
        else:
            response = "".join(agent_chat.run())
            print(f"""response: "{response}" """)
            # print_markdown(response)

        # Start interactive chat loop
        while True:
            try:
                # Get user input
                user_message = Prompt.ask("\n[blue]User[/blue]")
                if not user_message:
                    continue

                # Process user message
                if stream:
                    buffer = ""
                    for chunk in agent_chat.process_user_message(user_message):
                        buffer += chunk
                        to_print, buffer = _process_buffer(buffer)
                        if to_print:
                            print_markdown(to_print)
                    # Print any remaining content in the buffer
                    if buffer:
                        print_markdown(buffer)
                else:
                    response = "".join(agent_chat.process_user_message(user_message))
                    print(response)

            except (KeyboardInterrupt, EOFError):
                break
            except Exception as e:
                console.print(f"\n[red]Error: {str(e)}[/red]")
                break

        console.print("\n[yellow]Goodbye![/yellow]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
    except Exception as e:
        console.print(f"\n[red]Fatal error:[/red] {str(e)}")
        raise


if __name__ == "__main__":
    app()
