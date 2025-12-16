#!/usr/bin/env python
"""Command line interface for the playbooks framework.

Provides commands for running and compiling playbooks.
"""
import argparse
import asyncio
import importlib
import json
import os
import sys
import warnings
from typing import Any, Dict, List, Optional

import frontmatter
import openai
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from playbooks.compilation.compiler import Compiler, FileCompilationSpec
from playbooks.compilation.loader import Loader
from playbooks.core.exceptions import ProgramLoadError
from playbooks.infrastructure.logging.setup import configure_logging
from playbooks.utils.llm_config import LLMConfig
from playbooks.utils.version import get_playbooks_version

# Suppress deprecation warnings from external libraries
warnings.filterwarnings("ignore", category=DeprecationWarning, module="httpx")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="litellm")
warnings.filterwarnings("ignore", message="Accessing the 'model_fields' attribute")
warnings.filterwarnings("ignore", message="The `dict` method is deprecated")
warnings.filterwarnings(
    "ignore", message="Use 'content=<...>' to upload raw bytes/text content"
)

console = Console(stderr=True)  # All CLI diagnostics to stderr


def load_public_json_from_program(
    program_paths: List[str],
) -> Optional[List[Dict[str, Any]]]:
    """Load public.json from compiled playbook files.

    Args:
        program_paths: List of paths to playbook files

    Returns:
        List of public.json dictionaries (one per agent), or None if not available
    """
    import re

    try:
        # Load and compile program files
        program_file_tuples = Loader.read_program_files(program_paths)
        program_files = [
            FileCompilationSpec(file_path=fp, content=content, is_compiled=is_comp)
            for fp, content, is_comp in program_file_tuples
        ]

        # Check if all files are already compiled
        all_files_compiled = all(file_spec.is_compiled for file_spec in program_files)

        if all_files_compiled:
            # Use existing compiled files
            compiled_contents = [f.content for f in program_files]
        else:
            # Need to compile
            compiler = Compiler()
            compiled_results = asyncio.run(compiler.process_files(program_files))
            compiled_contents = [r.content for r in compiled_results]

        # Extract public.json from each compiled agent
        public_jsons = []
        for content in compiled_contents:
            matches = re.findall(r"```public\.json(.*?)```", content, re.DOTALL)
            if matches:
                for match in matches:
                    try:
                        public_json = json.loads(match)
                        if public_json:  # Skip empty lists
                            public_jsons.append(public_json)
                    except json.JSONDecodeError:
                        pass

        return public_jsons if public_jsons else None
    except Exception:
        # If we can't load public.json, return None (not a CLI utility)
        return None


def get_cli_entry_point(public_jsons: List[List[Dict]]) -> Optional[Dict]:
    """Find the CLI entry point from public.json data.

    Args:
        public_jsons: List of public.json dictionaries (one per agent)

    Returns:
        The CLI entry point playbook dict, or None if not found
    """
    if not public_jsons:
        return None

    # Look for playbook marked with cli_entry: true
    cli_entry_playbooks = []
    for agent_public_json in public_jsons:
        for playbook in agent_public_json:
            if playbook.get("cli_entry"):
                cli_entry_playbooks.append(playbook)

    # Error if multiple CLI entry points
    if len(cli_entry_playbooks) > 1:
        raise ValueError(
            f"Multiple playbooks marked with cli_entry:true. "
            f"Only one playbook can be the CLI entry point. "
            f"Found: {[p['name'] for p in cli_entry_playbooks]}"
        )

    if cli_entry_playbooks:
        return cli_entry_playbooks[0]

    # Look for first BGN playbook
    for agent_public_json in public_jsons:
        for playbook in agent_public_json:
            if playbook.get("is_bgn"):
                return playbook

    return None


def add_cli_arguments(parser: argparse.ArgumentParser, entry_point: Dict):
    """Add CLI arguments based on entry point playbook signature.

    Args:
        parser: Argparse parser to add arguments to
        entry_point: Entry point playbook dictionary with parameters
    """
    params = entry_point.get("parameters", {})
    properties = params.get("properties", {})
    required = params.get("required", [])

    for param_name, param_info in properties.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "")

        # Map JSON types to Python types
        type_mapping = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": lambda x: x.lower() in ["true", "1", "yes"],
        }

        python_type = type_mapping.get(param_type, str)

        parser.add_argument(
            f"--{param_name}",
            type=python_type,
            required=(param_name in required),
            help=param_desc,
        )


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
    program_file_tuples = Loader.read_program_files(program_paths)
    program_files = [
        FileCompilationSpec(file_path=fp, content=content, is_compiled=is_comp)
        for fp, content, is_comp in program_file_tuples
    ]

    # Let compiler handle all compilation logic
    compiler = Compiler()
    compiled_results = asyncio.run(compiler.process_files(program_files))

    try:
        for result in compiled_results:
            # Add frontmatter back to content if present
            content = result.content
            if result.frontmatter_dict:
                fm_post = frontmatter.Post(content, **result.frontmatter_dict)
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
    enable_debug: bool = False,
    debug_host: str = "127.0.0.1",
    debug_port: int = 7529,
    wait_for_client: bool = False,
    stop_on_entry: bool = False,
    snoop: bool = False,
    initial_state: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
) -> None:
    """
    Run a playbook using the specified application.

    Args:
        application_module: Module path like 'playbooks.applications.agent_chat'
        program_paths: List of playbook files to run
        verbose: Whether to print the session log
        enable_debug: Whether to start the debug server
        debug_host: Host address for the debug server
        debug_port: Port for the debug server
        wait_for_client: Whether to wait for a client to connect before starting
        stop_on_entry: Whether to stop at the beginning of playbook execution
        snoop: Whether to display agent-to-agent messages
        initial_state: Optional initial state variables to set on agents
        message: Optional message to send from human to first AI agent after initialization
    """
    # Import the application module
    try:
        LLMConfig()  # Check if API key is set for selected model
        module = importlib.import_module(application_module)
    except ModuleNotFoundError as e:
        console.print(f"[bold red]Error importing application:[/bold red] {e}")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)

    if isinstance(program_paths, str):
        program_paths = [program_paths]

    try:
        await module.main(
            program_paths=program_paths,
            verbose=verbose,
            stream=stream,
            enable_debug=enable_debug,
            debug_host=debug_host,
            debug_port=debug_port,
            wait_for_client=wait_for_client,
            stop_on_entry=stop_on_entry,
            snoop=snoop,
            initial_state=initial_state,
            message=message,
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


# -------------------------
# config show implementation
# -------------------------


def _mask_secrets_inplace(obj: Any) -> Any:
    """
    Recursively mask values whose keys look secret-ish.
    Heuristic: key contains one of KEY, TOKEN, SECRET, PASSWORD (case-insensitive).
    """
    if isinstance(obj, dict):
        masked = {}
        for k, v in obj.items():
            if isinstance(k, str) and any(
                s in k.lower() for s in ("key", "token", "secret", "password")
            ):
                masked[k] = "********"
            else:
                masked[k] = _mask_secrets_inplace(v)
        return masked
    if isinstance(obj, list):
        return [_mask_secrets_inplace(v) for v in obj]
    return obj


def _print_config_pretty(effective: dict, files_used: list[str], mask: bool) -> None:
    """Pretty render config and file list using rich."""
    if mask:
        effective = _mask_secrets_inplace(effective)

    table = Table(title="Effective Playbooks Configuration", show_lines=False)
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    def walk(prefix: str, node: Any):
        if isinstance(node, dict):
            for k in sorted(node.keys()):
                walk(f"{prefix}.{k}" if prefix else k, node[k])
        else:
            # Render scalars/arrays as JSON for readability
            table.add_row(prefix, json.dumps(node, ensure_ascii=False))

    walk("", effective)
    console.print(table)

    if files_used:
        files_panel = Panel.fit(
            "\n".join(files_used),
            title="Files used (lowest → highest among files)",
            border_style="magenta",
        )
        console.print(files_panel)


def _cmd_config_show(args) -> None:
    # Lazy import so CLI still works if config module is missing in other contexts
    try:
        from .config import load_config
    except Exception as e:
        console.print(
            "[bold red]Unable to load configuration module (.config).[/bold red]\n"
            "Make sure `config.py` (with load_config) is available in the package."
        )
        console.print(f"[red]Detail:[/red] {e}")
        sys.exit(1)

    profile = args.profile
    explicit_path = args.config_path
    overrides = {}  # reserved for future: map additional CLI flags to schema here

    try:
        config, files = load_config(
            profile=profile,
            explicit_path=explicit_path,
            overrides=overrides,
        )
    except Exception as e:
        console.print(f"[bold red]Config error:[/bold red] {e}")
        sys.exit(1)

    effective = config.model_dump()

    if args.json:
        if args.mask_secrets:
            effective = _mask_secrets_inplace(effective)
        # Include files in JSON if requested
        payload = {"config": effective, "files_used": [str(p) for p in files]}
        console.print_json(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    # Pretty (default)
    _print_config_pretty(effective, [str(p) for p in files], args.mask_secrets)


def main():
    """Main CLI entry point."""
    import sys

    # Always print banner to stderr (diagnostics)
    print("-" * 80, file=sys.stderr)
    print(f"Playbooks {get_playbooks_version()}", file=sys.stderr)
    print("-" * 80, file=sys.stderr)

    # Configure logging early
    configure_logging()

    # Check for --quiet flag to suppress stderr diagnostics
    quiet_mode = "--quiet" in sys.argv
    if quiet_mode:
        import logging

        logging.getLogger().setLevel(logging.WARNING)
        # Suppress specific noisy loggers
        logging.getLogger("mcp.client.streamable_http").setLevel(logging.WARNING)
        logging.getLogger("playbooks.agents.mcp_agent").setLevel(logging.WARNING)
        logging.getLogger("playbooks.agents.remote_ai_agent").setLevel(logging.WARNING)
        logging.getLogger("playbooks.compilation.compiler").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(
        description="Playbooks CLI - Compile and run Playbooks programs",
        prog="playbooks",
    )

    # Add version argument
    parser.add_argument(
        "--version", action="version", version=f"playbooks {get_playbooks_version()}"
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
    run_parser.add_argument(
        "--snoop",
        type=lambda x: x.lower() in ["true", "1", "yes"],
        default=False,
        help="Display messages exchanged between agents (default: False). Use --snoop=true to see all agent-to-agent communication",
    )

    # CLI utility mode flags (always available)
    run_parser.add_argument(
        "--message",
        help="Natural language message to pass to the agent",
    )
    run_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all output except agent messages (no version banner, logs, or agent name prefixes)",
    )
    run_parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Fail if interactive input is required (for CI/CD pipelines)",
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
        "--http-port", type=int, default=8080, help="HTTP port (default: 8080)"
    )
    webserver_parser.add_argument(
        "--ws-port", type=int, default=8081, help="WebSocket port (default: 8081)"
    )

    # Playground command
    playground_parser = subparsers.add_parser(
        "playground", help="Start the Playbooks playground (webserver + browser)"
    )
    playground_parser.add_argument(
        "--host", default="localhost", help="Host address (default: localhost)"
    )
    playground_parser.add_argument(
        "--http-port", type=int, default=8080, help="HTTP port (default: 8080)"
    )
    playground_parser.add_argument(
        "--ws-port", type=int, default=8081, help="WebSocket port (default: 8081)"
    )

    # -------------------------
    # Config command group
    # -------------------------
    config_parser = subparsers.add_parser(
        "config", help="Inspect and manage Playbooks configuration"
    )
    cfg_sub = config_parser.add_subparsers(dest="config_cmd", required=True)

    cfg_show = cfg_sub.add_parser(
        "show", help="Show effective configuration and sources"
    )
    cfg_show.add_argument(
        "--profile",
        default=os.getenv("PLAYBOOKS_PROFILE"),
        help="Profile name to apply (e.g., prod). Defaults to $PLAYBOOKS_PROFILE.",
    )
    cfg_show.add_argument(
        "--config",
        dest="config_path",
        help="Explicit config file to load in addition to project/user files.",
    )
    cfg_show.add_argument(
        "--mask-secrets",
        action="store_true",
        help="Mask likely secrets (keys containing key/token/secret/password).",
    )
    cfg_show.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of a table (includes files_used).",
    )

    # First parse to get command and program_paths, allowing unknown args
    args, unknown_args = parser.parse_known_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "run":
        # Try to load public.json to see if this has CLI parameters
        try:
            public_jsons = load_public_json_from_program(args.program_paths)
            entry_point = get_cli_entry_point(public_jsons) if public_jsons else None
        except Exception:
            # If loading public.json fails, no entry point
            entry_point = None

        # If entry point found with parameters, add them to argparse
        if entry_point and entry_point.get("parameters", {}).get("properties"):
            # Add dynamic CLI arguments based on entry point signature
            add_cli_arguments(run_parser, entry_point)

            # Re-parse with dynamic arguments (now they're recognized)
            args = parser.parse_args()

            # Extract CLI args (parameters from entry point)
            cli_args = {}
            params = entry_point.get("parameters", {})
            properties = params.get("properties", {})
            for param_name in properties.keys():
                if hasattr(args, param_name):
                    value = getattr(args, param_name)
                    if value is not None:
                        cli_args[param_name] = value

            # Check stdin for piped input
            stdin_content = None
            if not sys.stdin.isatty():
                stdin_content = sys.stdin.read()

            try:
                from playbooks.applications import cli_utility

                exit_code = asyncio.run(
                    cli_utility.main(
                        program_paths=args.program_paths,
                        cli_args=cli_args,
                        message=args.message,
                        stdin_content=stdin_content,
                        non_interactive=args.non_interactive,
                        quiet=args.quiet,
                        stream=args.stream,
                        verbose=args.verbose,
                        snoop=args.snoop,
                    )
                )
                sys.exit(exit_code)
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted by user[/yellow]")
                sys.exit(130)
            except ProgramLoadError as e:
                console.print(f"[red]Error loading program:[/red] {e}")
                sys.exit(1)

        # No entry point found or not a CLI utility - run in interactive mode
        # Handle stdin and message separately
        initial_state = {}
        stdin_content = None
        if not sys.stdin.isatty():
            stdin_content = sys.stdin.read()
            if stdin_content:
                # Set startup_message only if stdin is provided
                initial_state["startup_message"] = stdin_content

        # Get message if provided (will be sent as user message after initialization)
        message = None
        if hasattr(args, "message") and args.message:
            message = args.message

        try:
            asyncio.run(
                run_application(
                    args.application,
                    args.program_paths,
                    verbose=args.verbose,
                    stream=args.stream,
                    enable_debug=args.debug,
                    debug_host=args.debug_host,
                    debug_port=args.debug_port,
                    wait_for_client=args.wait_for_client,
                    stop_on_entry=args.stop_on_entry,
                    snoop=args.snoop,
                    initial_state=initial_state if initial_state else None,
                    message=message,
                )
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user[/yellow]")
        except ProgramLoadError as e:
            console.print(f"[red]Error loading program:[/red] {e}")
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
            import threading
            import time
            import webbrowser
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

    elif args.command == "config":
        if args.config_cmd == "show":
            _cmd_config_show(args)
        else:
            console.print("[red]Unknown config subcommand[/red]")
            sys.exit(2)


if __name__ == "__main__":
    main()
