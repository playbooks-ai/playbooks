from typing import List, Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.prompt import Prompt

from playbooks.core.loader import load
from playbooks.core.runtime import RuntimeConfig, SingleThreadedPlaybooksRuntime

load_dotenv()

app = typer.Typer()
console = Console()

PLAYBOOK_PATHS_ARG = typer.Argument(
    ..., help="One or more paths to playbook files. Supports glob patterns"
)


def print_markdown(text: str):
    """Print text as markdown using rich"""
    md = Markdown(text)
    console.print(md)


def print_streaming_markdown(stream_iterator):
    """Print streaming markdown content"""
    content = ""
    with Live(Markdown(content), refresh_per_second=10) as live:
        for chunk in stream_iterator:
            content += chunk
            live.update(Markdown(content))


@app.command()
def chat(
    playbook_paths: List[str] = PLAYBOOK_PATHS_ARG,
    llm: str = typer.Option(
        None, help="LLM provider to use (openai, anthropic, vertexai)"
    ),
    model: str = typer.Option(None, help="Model name for the selected LLM"),
    api_key: Optional[str] = typer.Option(None, help="API key for the selected LLM"),
    stream: bool = typer.Option(False, help="Enable streaming output from LLM"),
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
    if playbook_paths is None:
        playbook_paths = PLAYBOOK_PATHS_ARG

    try:
        # Load playbooks
        console.print(f"\nLoading playbooks from: {playbook_paths}")
        combined_playbooks = load(playbook_paths)
        console.print("\nLoaded playbooks successfully")

        # Initialize runtime with selected LLM
        console.print(
            f"\nInitializing runtime with model={model}, api_key={'*' * len(api_key) if api_key else None}"
        )
        config = RuntimeConfig(model=model, api_key=api_key)
        runtime = SingleThreadedPlaybooksRuntime(config)
        console.print("\nRuntime initialized successfully")

        # Start chat loop
        while True:
            try:
                console.print("\nWaiting for user input...")
                user_input = Prompt.ask("\n[blue]User[/blue]")
                console.print(f"\nReceived user input: {user_input}")

                if user_input.lower() in ["exit", "quit"]:
                    console.print("\nExiting chat loop...")
                    break

                try:
                    console.print("\n[yellow]Agent: [/yellow]")
                    if stream:
                        console.print("\nStarting streaming response...")
                        response_stream = runtime.stream(
                            combined_playbooks, user_message=user_input
                        )
                        print_streaming_markdown(response_stream)
                    else:
                        console.print("\nGetting non-streaming response...")
                        response = await runtime.run(
                            combined_playbooks, user_message=user_input
                        )
                        print_markdown(response)
                except Exception as e:
                    console.print(f"\n[red]Error during response:[/red] {str(e)}")
                    raise

            except Exception as e:
                console.print(f"\n[red]Error in chat loop:[/red] {str(e)}")
                raise

    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
    except Exception as e:
        console.print(f"\n[red]Fatal error:[/red] {str(e)}")
        raise


def main():
    app()


if __name__ == "__main__":
    main()
