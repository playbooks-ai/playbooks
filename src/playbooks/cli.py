#!/usr/bin/env python
"""
Command line interface for the playbooks framework.

Provides commands for running and compiling playbooks.
"""
import argparse
import asyncio
import importlib
import sys
import warnings
from typing import List

import frontmatter
import openai
from rich.console import Console

from .compiler import Compiler
from .exceptions import ProgramLoadError
from .loader import Loader
from .logging_setup import configure_logging
from .utils.llm_config import LLMConfig

# Suppress deprecation warnings from external libraries
warnings.filterwarnings("ignore", category=DeprecationWarning, module="httpx")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="litellm")
warnings.filterwarnings("ignore", message="Accessing the 'model_fields' attribute")
warnings.filterwarnings("ignore", message="The `dict` method is deprecated")
warnings.filterwarnings(
    "ignore", message="Use 'content=<...>' to upload raw bytes/text content"
)

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
        program_paths: List of Playbooks program files to compile
        output_file: Optional path to save compiled output. If None, prints to stdout.
    """
    if isinstance(program_paths, str):
        program_paths = [program_paths]

    # Load files individually
    program_files = Loader.read_program_files(program_paths)

    # Let compiler handle all compilation logic
    llm_config = LLMConfig()
    compiler = Compiler(llm_config)
    compiled_results = compiler.process_files(program_files)

    try:
        for _, frontmatter_dict, content, _ in compiled_results:
            # Add frontmatter back to content if present
            if frontmatter_dict:
                fm_post = frontmatter.Post(content, **frontmatter_dict)
                content = frontmatter.dumps(fm_post)

            if output_file:
                # Save to specified output file
                if len(compiled_results) > 1:
                    raise Exception(
                        "Do not specify output file name when compiling multiple files"
                    )

                with open(output_file, "w") as f:
                    f.write(content)
                console.print(
                    f"[green]Compiled Playbooks program saved to:[/green] {output_file}"
                )
            else:
                print(content)

    except Exception as e:
        console.print(f"[bold red]Error compiling Playbooks program:[/bold red] {e}")
        sys.exit(1)


async def run_application(
    application_module: str,
    program_paths: List[str],
    verbose: bool = False,
    stream: bool = True,
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
            stream=stream,
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
    # Configure logging early
    configure_logging()

    parser = argparse.ArgumentParser(
        description="Playbooks CLI - Compile and run Playbooks programs",
        prog="playbooks",
    )

    # Add version argument
    parser.add_argument(
        "--version", action="version", version=f"playbooks {get_version()}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a Playbooks program")
    run_parser.add_argument(
        "program_paths",
        help="One or more paths to the Playbooks program files to run",
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
        "--stream",
        type=lambda x: x.lower() in ["true", "1", "yes"],
        default=True,
        help="Enable/disable streaming output (default: True). Use --stream=False for buffered output",
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
        help="Skip compilation step (skipped automatically for .pbasm files)",
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

    # Webserver command
    webserver_parser = subparsers.add_parser(
        "webserver", help="Start the Playbooks web server"
    )
    webserver_parser.add_argument(
        "--host", default="localhost", help="Host address (default: localhost)"
    )
    webserver_parser.add_argument(
        "--http-port", type=int, default=8000, help="HTTP port (default: 8000)"
    )
    webserver_parser.add_argument(
        "--ws-port", type=int, default=8001, help="WebSocket port (default: 8001)"
    )

    # Playground command
    playground_parser = subparsers.add_parser(
        "playground", help="Start the Playbooks playground (webserver + browser)"
    )
    playground_parser.add_argument(
        "--host", default="localhost", help="Host address (default: localhost)"
    )
    playground_parser.add_argument(
        "--http-port", type=int, default=8000, help="HTTP port (default: 8000)"
    )
    playground_parser.add_argument(
        "--ws-port", type=int, default=8001, help="WebSocket port (default: 8001)"
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
                    stream=args.stream,
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
        except openai.OpenAIError:
            import traceback

            traceback.print_exc()
            console.print(
                "[bold red]Error: Authentication failed. Please make sure you have a valid ANTHROPIC_API_KEY environment variable set.[/bold red]"
            )
            sys.exit(1)
        except ProgramLoadError as e:
            console.print(f"[bold red]Error loading program:[/bold red] {e}")
            sys.exit(1)
        except Exception as e:
            console.print(f"[bold red]Error compiling playbooks:[/bold red] {e}")
            sys.exit(1)

    elif args.command == "webserver":
        try:
            # Import here to avoid unnecessary imports if not using webserver
            from .applications.web_server import PlaybooksWebServer

            async def start_webserver():
                server = PlaybooksWebServer(args.host, args.http_port, args.ws_port)
                await server.start()

            asyncio.run(start_webserver())
        except KeyboardInterrupt:
            console.print("\n[yellow]Web server stopped[/yellow]")
        except Exception as e:
            console.print(f"[bold red]Error starting web server:[/bold red] {e}")
            sys.exit(1)

    elif args.command == "playground":
        try:
            import webbrowser
            import threading
            import time
            from pathlib import Path

            # Import here to avoid unnecessary imports if not using webserver
            from .applications.web_server import PlaybooksWebServer

            # Get the path to the playground HTML file
            playground_path = (
                Path(__file__).parent / "applications" / "playbooks_playground.html"
            )
            playground_url = f"file://{playground_path.absolute()}"

            console.print("[green]Starting Playbooks Playground...[/green]")
            console.print(
                f"[cyan]Server will start on:[/cyan] http://{args.host}:{args.http_port}"
            )
            console.print(
                f"[cyan]WebSocket will start on:[/cyan] ws://{args.host}:{args.ws_port}"
            )

            # Function to open browser after a short delay
            def open_browser():
                time.sleep(2)  # Give server time to start
                console.print(
                    f"[green]Opening playground in browser:[/green] {playground_url}"
                )
                webbrowser.open(playground_url)

            # Start browser opener in background thread
            browser_thread = threading.Thread(target=open_browser, daemon=True)
            browser_thread.start()

            async def start_playground():
                server = PlaybooksWebServer(args.host, args.http_port, args.ws_port)
                console.print(f"[yellow]Playground URL:[/yellow] {playground_url}")
                console.print("[dim]Press Ctrl+C to stop[/dim]")
                await server.start()

            asyncio.run(start_playground())

        except KeyboardInterrupt:
            console.print("\n[yellow]Playground stopped[/yellow]")
        except Exception as e:
            console.print(f"[bold red]Error starting playground:[/bold red] {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
