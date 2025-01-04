"""Command-line interface for playbooks."""

from typing import List, Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Prompt

from playbooks.cli.session import ChatSession

load_dotenv()

app = typer.Typer()
console = Console()

PLAYBOOK_PATHS_ARG = typer.Argument(
    ..., help="One or more paths to playbook files. Supports glob patterns"
)


@app.command()
def chat(
    playbook_paths: List[str] = PLAYBOOK_PATHS_ARG,
    llm: str = typer.Option(
        None, help="LLM provider to use (openai, anthropic, vertexai)"
    ),
    model: str = typer.Option(None, help="Model name for the selected LLM"),
    api_key: Optional[str] = typer.Option(None, help="API key for the selected LLM"),
    stream: bool = typer.Option(True, help="Enable streaming output from LLM"),
):
    """Start an interactive chat session using the specified playbooks and LLM"""
    import asyncio

    asyncio.run(_async_chat(playbook_paths, llm, model, api_key, stream))


async def _async_chat(
    playbook_paths: List[str],
    llm: Optional[str],
    model: Optional[str],
    api_key: Optional[str],
    stream: bool,
):
    """Run the async chat session"""
    session = ChatSession(playbook_paths, llm, model, api_key, stream)

    try:
        await session.initialize()

        # Process initial "Begin" message
        await session.process_user_input("Begin")

        while True:
            try:
                user_input = Prompt.ask("\n[blue]User[/blue]")

                if not await session.process_user_input(user_input):
                    break

            except Exception as e:
                console.print(f"\n[red]Error in chat loop:[/red] {str(e)}")
                raise

    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
        session.cleanup()
    except Exception as e:
        console.print(f"\n[red]Fatal error:[/red] {str(e)}")
        session.cleanup()
        raise


def main():
    app()


if __name__ == "__main__":
    main()
