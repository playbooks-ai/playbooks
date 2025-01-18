"""Command-line interface for playbooks."""

import asyncio
from typing import List, Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Prompt

from playbooks.cli.output import print_markdown, print_streaming_markdown
from playbooks.core.db.runtime_session import RuntimeSession

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
    asyncio.run(_async_chat(playbook_paths, llm, model, api_key, stream))


async def _async_chat(
    playbook_paths: List[str],
    llm: Optional[str],
    model: Optional[str],
    api_key: Optional[str],
    stream: bool,
):
    """Run the async chat session"""
    session = RuntimeSession(playbook_paths, llm, model, api_key, stream)

    try:
        console.print(f"\nLoading playbooks from: {playbook_paths}")
        await session.initialize()
        console.print("\nLoaded playbooks successfully")
        console.print(
            f"\nInitializing runtime with model={model}, "
            f"api_key={'*' * len(api_key) if api_key else None}"
        )
        console.print("\nRuntime initialized successfully")

        # Process initial "Begin" message
        console.print("\n[yellow]Agent: [/yellow]")
        response = await session.process_user_input("Begin")
        if stream:
            await print_streaming_markdown(response)
        else:
            print_markdown(response)

        while True:
            try:
                user_input = Prompt.ask("\n[blue]User[/blue]")
                if user_input.lower() in ["exit", "quit"]:
                    console.print("\nExiting chat loop...")
                    session.cleanup()
                    return

                console.print("\n[yellow]Agent: [/yellow]")
                response = await session.process_user_input(user_input)
                if stream:
                    await print_streaming_markdown(response)
                else:
                    print_markdown(response)

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
