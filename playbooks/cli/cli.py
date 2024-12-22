import sys
import typer
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt
from typing import Optional, List

from playbooks.core.loader import load
from playbooks.core.runner import run
from playbooks.core.runner import PlaybookRunner

app = typer.Typer()
console = Console()

def print_markdown(text: str):
    """Print text as markdown using rich"""
    md = Markdown(text)
    console.print(md)


@app.command()
def chat(
    playbook_paths: List[str] = typer.Argument(
        ...,
        help="One or more paths to playbook files. Supports glob patterns"
    ),
    llm: str = typer.Option(
        None,
        help="LLM provider to use (openai, anthropic, vertexai)"
    ),
    model: str = typer.Option(
        None,
        help="Model name for the selected LLM"
    ),
    api_key: Optional[str] = typer.Option(
        None,
        help="API key for the selected LLM"
    )
):
    """Start an interactive chat session using the specified playbooks and LLM"""
    
    try:
        # Load playbooks
        playbook_paths = playbook_paths[1:]
        combined_playbooks = load(playbook_paths)
        
        # Initialize runner with selected LLM
        runner = PlaybookRunner(
            llm=llm,
            api_key=api_key,
            model=model
        )
        
        # Start chat loop
        while True:
            user_input = Prompt.ask("\nYou")
            if user_input.lower() in ("exit", "quit"):
                break
                
            try:
                response = runner.run(combined_playbooks, user_input=user_input)
                console.print("\n[yellow]Agent: [/yellow]")
                print_markdown(response)
            except Exception as e:
                console.print(f"\n[red]Error:[/red] {str(e)}")
                
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")

def main():
    app()

if __name__ == "__main__":
    main() 