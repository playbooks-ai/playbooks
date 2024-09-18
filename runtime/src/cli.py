import os
import sys

import click
from dotenv import load_dotenv

from .main import PlaybookRuntime

# Load environment variables from .env file
load_dotenv()


@click.command()
@click.option(
    "--project", help="Path to the project folder containing playbooks and config.json"
)
@click.option(
    "--model", default="anthropic/claude-3-sonnet-20240229", help="LLM model to use"
)
def cli(project: str, model: str):
    # Check if ANTHROPIC_API_KEY is set
    if "ANTHROPIC_API_KEY" not in os.environ:
        click.echo(
            "Error: ANTHROPIC_API_KEY not found in environment variables or .env file."
        )
        sys.exit(1)

    runtime = PlaybookRuntime(project, model)
    click.echo("Chat session started. Type 'exit' to quit.")

    # Generate and display welcome message
    click.echo("AI: ", nl=False)
    for chunk in runtime.chat("Start the conversation"):
        click.echo(chunk, nl=False)
        sys.stdout.flush()
    click.echo("\n")  # New line after the welcome message

    while True:
        user_input = click.prompt("You")
        if user_input.lower() == "exit":
            break

        click.echo("AI: ", nl=False)
        for chunk in runtime.chat(user_input):
            click.echo(chunk, nl=False)
            sys.stdout.flush()
        click.echo()  # New line after the complete response


if __name__ == "__main__":
    cli()
