#!/usr/bin/env python
"""
Command line interface for the playbooks framework.

Provides commands for running and compiling playbooks.
"""
import argparse
import asyncio
import importlib
import sys
from typing import List

from rich.console import Console

from .compiler import Compiler
from .exceptions import ProgramLoadError
from .loader import Loader
from .utils.llm_config import LLMConfig

console = Console()


def get_version() -> str:
    """Get the version of the playbooks package."""
    try:
        from importlib.metadata import version

        return version("playbooks")
    except ImportError:
        # Fallback for Python < 3.8
        try:
            from importlib_metadata import version

            return version("playbooks")
        except ImportError:
            return "unknown"
    except Exception:
        return "unknown"


def compile(program_paths: List[str], output_file: str = None) -> None:
    """
    Compile a playbook file.

    Args:
        program_paths: List of playbook files to compile
        output_file: Optional path to save compiled output. If None, prints to stdout.
    """
    if isinstance(program_paths, str):
        program_paths = [program_paths]

    program_content, do_not_compile = Loader.read_program(program_paths)

    # Skip compilation if any of the files are already compiled (.pbc)
    if do_not_compile:
        # For compiled files, use the content as-is without compilation
        compiled_content = program_content
    else:
        llm_config = LLMConfig()
        compiler = Compiler(llm_config)
        compiled_content = compiler.process(program_content)

    try:
        if output_file:
            # Save to file
            with open(output_file, "w") as f:
                f.write(compiled_content)
            console.print(f"[green]Compiled playbook saved to:[/green] {output_file}")
        else:
            # Print to stdout
            print(compiled_content)

    except Exception as e:
        console.print(f"[bold red]Error compiling playbooks:[/bold red] {e}")
        sys.exit(1)


async def run_application(
    application_module: str,
    program_paths: List[str],
    verbose: bool = False,
    debug: bool = False,
    debug_host: str = "127.0.0.1",
    debug_port: int = 7529,
    wait_for_client: bool = False,
    stop_on_entry: bool = False,
) -> None:
    """
    Run a playbook using the specified application.

    Args:
        application_module: Module path like 'playbooks.applications.agent_chat'
        program_paths: List of playbook files to run
        verbose: Whether to print the session log
        debug: Whether to start the debug server
        debug_host: Host address for the debug server
        debug_port: Port for the debug server
        wait_for_client: Whether to wait for a client to connect before starting
        stop_on_entry: Whether to stop at the beginning of playbook execution
    """
    # Import the application module
    try:
        module = importlib.import_module(application_module)
    except ModuleNotFoundError as e:
        console.print(f"[bold red]Error importing application:[/bold red] {e}")
        sys.exit(1)

    if isinstance(program_paths, str):
        program_paths = [program_paths]

    try:
        await module.main(
            program_paths=program_paths,
            verbose=verbose,
            debug=debug,
            debug_host=debug_host,
            debug_port=debug_port,
            wait_for_client=wait_for_client,
            stop_on_entry=stop_on_entry,
        )

    except ImportError as e:
        console.print(f"[bold red]Error importing application:[/bold red] {e}")
        console.print(
            f"[yellow]Make sure the module path is correct: {application_module}[/yellow]"
        )
        sys.exit(1)
    except Exception as e:
        import traceback

        console.print(f"[bold red]Error running application:[/bold red] {e}")
        console.print("[bold red]Traceback:[/bold red]")
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Playbooks CLI - Run and compile playbooks", prog="playbooks"
    )

    # Add version argument
    parser.add_argument(
        "--version", action="version", version=f"playbooks {get_version()}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a playbook with an application")
    run_parser.add_argument(
        "program_paths",
        help="One or more paths to the playbook files to run",
        nargs="+",
    )
    run_parser.add_argument(
        "--application",
        default="playbooks.applications.agent_chat",
        help="Application module to use (default: playbooks.applications.agent_chat)",
    )
    run_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print the session log"
    )
    run_parser.add_argument(
        "--debug", action="store_true", help="Start the debug server"
    )
    run_parser.add_argument(
        "--debug-host",
        default="127.0.0.1",
        help="Debug server host (default: 127.0.0.1)",
    )
    run_parser.add_argument(
        "--debug-port", type=int, default=7529, help="Debug server port (default: 7529)"
    )
    run_parser.add_argument(
        "--wait-for-client",
        action="store_true",
        help="Wait for a debug client to connect before starting execution",
    )
    run_parser.add_argument(
        "--skip-compilation",
        action="store_true",
        help="Skip compilation step (automatically enabled for .pbc files)",
    )
    run_parser.add_argument(
        "--stop-on-entry",
        action="store_true",
        help="Stop at the beginning of playbook execution",
    )

    # Compile command
    compile_parser = subparsers.add_parser("compile", help="Compile a playbook")
    compile_parser.add_argument(
        "program_paths",
        help="One or more paths to the playbook files to compile",
        nargs="+",
    )
    compile_parser.add_argument(
        "--output", help="Output file path (if not specified, prints to stdout)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "run":
        # Run the application
        try:
            asyncio.run(
                run_application(
                    args.application,
                    args.program_paths,
                    verbose=args.verbose,
                    debug=args.debug,
                    debug_host=args.debug_host,
                    debug_port=args.debug_port,
                    wait_for_client=args.wait_for_client,
                    stop_on_entry=args.stop_on_entry,
                )
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user[/yellow]")
        except ProgramLoadError as e:
            console.print(f"[bold red]Error loading program:[/bold red] {e}")
            sys.exit(1)

    elif args.command == "compile":
        try:
            compile(
                args.program_paths,
                args.output,
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user[/yellow]")
        except ProgramLoadError as e:
            console.print(f"[bold red]Error loading program:[/bold red] {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
