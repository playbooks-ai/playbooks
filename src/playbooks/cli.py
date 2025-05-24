#!/usr/bin/env python
"""
Command line interface for the playbooks framework.

Provides commands for running and compiling playbooks.
"""
import argparse
import asyncio
import importlib
import sys
from pathlib import Path
from typing import List

from rich.console import Console

from .compiler import Compiler
from .loader import Loader
from .utils.llm_config import LLMConfig

console = Console()


def compile_playbook(input_file: str, output_file: str = None) -> None:
    """
    Compile a playbook file.

    Args:
        input_file: Path to the input playbook file
        output_file: Optional path to save compiled output. If None, prints to stdout.
    """
    try:
        # Read the input file
        program_content = Loader.read_program([input_file])

        # Initialize compiler with default LLM config
        llm_config = LLMConfig()
        compiler = Compiler(llm_config)

        # Compile the program
        compiled_content = compiler.process(program_content)

        if output_file:
            # Save to file
            with open(output_file, "w") as f:
                f.write(compiled_content)
            console.print(f"[green]Compiled playbook saved to:[/green] {output_file}")
        else:
            # Print to stdout
            print(compiled_content)

    except Exception as e:
        console.print(f"[bold red]Error compiling playbook:[/bold red] {e}")
        sys.exit(1)


async def run_application(application_module: str, playbook_files: List[str]) -> None:
    """
    Run a playbook using the specified application.

    Args:
        application_module: Module path like 'playbooks.applications.agent_chat'
        playbook_files: List of playbook files to run
    """
    try:
        # Import the application module
        module = importlib.import_module(application_module)

        # Check if the module has a main function
        if not hasattr(module, "main"):
            console.print(
                f"[bold red]Error:[/bold red] Module {application_module} does not have a 'main' function"
            )
            sys.exit(1)

        # Convert file list to a glob pattern for compatibility with existing applications
        if len(playbook_files) == 1:
            glob_path = playbook_files[0]
        else:
            # For multiple files, we'll need to handle this differently
            # For now, just use the first file
            glob_path = playbook_files[0]
            if len(playbook_files) > 1:
                console.print(
                    "[yellow]Warning: Multiple files specified, using only the first one[/yellow]"
                )

        # Call the main function with default parameters
        await module.main(
            glob_path=glob_path,
            verbose=False,
            debug=False,
            debug_host="127.0.0.1",
            debug_port=7529,
            wait_for_client=False,
        )

    except ImportError as e:
        console.print(f"[bold red]Error importing application:[/bold red] {e}")
        console.print(
            f"[yellow]Make sure the module path is correct: {application_module}[/yellow]"
        )
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error running application:[/bold red] {e}")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Playbooks CLI - Run and compile playbooks", prog="playbooks"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a playbook with an application")
    run_parser.add_argument("playbook", help="Path to the playbook file")
    run_parser.add_argument(
        "--application",
        default="playbooks.applications.agent_chat",
        help="Application module to use (default: playbooks.applications.agent_chat)",
    )

    # Compile command
    compile_parser = subparsers.add_parser("compile", help="Compile a playbook")
    compile_parser.add_argument("playbook", help="Path to the playbook file to compile")
    compile_parser.add_argument(
        "--output", help="Output file path (if not specified, prints to stdout)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "run":
        # Validate that the playbook file exists
        if not Path(args.playbook).exists():
            console.print(
                f"[bold red]Error:[/bold red] Playbook file not found: {args.playbook}"
            )
            sys.exit(1)

        # Run the application
        try:
            asyncio.run(run_application(args.application, [args.playbook]))
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user[/yellow]")

    elif args.command == "compile":
        # Validate that the playbook file exists
        if not Path(args.playbook).exists():
            console.print(
                f"[bold red]Error:[/bold red] Playbook file not found: {args.playbook}"
            )
            sys.exit(1)

        # Compile the playbook
        compile_playbook(args.playbook, args.output)


if __name__ == "__main__":
    main()
