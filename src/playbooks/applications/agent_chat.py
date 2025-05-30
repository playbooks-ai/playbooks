#!/usr/bin/env python
"""
CLI application for interactive agent chat using playbooks.
Provides a simple terminal interface for communicating with AI agents.
"""
import argparse
import asyncio
import functools
import sys
import uuid
from pathlib import Path
from typing import Callable, List

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from playbooks import Playbooks
from playbooks.base_agent import AgentCommunicationMixin
from playbooks.constants import EOM
from playbooks.events import Event
from playbooks.markdown_playbook_execution import ExecutionFinished
from playbooks.playbook_call import PlaybookCall
from playbooks.session_log import SessionLogItemLevel

# Add the src directory to the Python path to import playbooks
sys.path.insert(0, str(Path(__file__).parent.parent))

# Initialize Rich console
console = Console()


class PubSub:
    """Simple publish-subscribe mechanism for event handling."""

    def __init__(self):
        self.subscribers: List[Callable] = []

    def subscribe(self, callback: Callable):
        """Subscribe a callback function to receive messages."""
        self.subscribers.append(callback)

    def publish(self, message):
        """Publish a message to all subscribers."""
        for subscriber in self.subscribers:
            subscriber(message)


class SessionLogWrapper:
    """Wrapper around session_log that publishes updates."""

    def __init__(self, session_log, pubsub, verbose=False, agent=None):
        self._session_log = session_log
        self._pubsub = pubsub
        self.verbose = verbose
        self.agent = agent

    def append(self, msg, level=SessionLogItemLevel.MEDIUM):
        """Append a message to the session log and publish it."""
        self._session_log.append(msg, level)
        # Always publish messages related to SendMessage to human
        if (
            isinstance(msg, PlaybookCall)
            and msg.playbook_klass == "SendMessage"
            and msg.args
            and msg.args[0] == "human"
        ):
            # Use the agent's class/type as the display name
            agent_name = self.agent.klass if self.agent else "Agent"

            # Create a styled message with Rich
            message_text = Text(msg.args[1])
            console.print()  # Add a newline for spacing
            console.print(
                Panel(
                    message_text,
                    title=agent_name,
                    border_style="cyan",
                    title_align="left",
                    expand=False,
                )
            )

        if self.verbose:
            self._pubsub.publish(str(msg))

    def __iter__(self):
        return iter(self._session_log)

    def __str__(self):
        return str(self._session_log)


# Store original method for restoring later
original_wait_for_message = AgentCommunicationMixin.WaitForMessage


@functools.wraps(original_wait_for_message)
async def patched_wait_for_message(self, source_agent_id: str):
    """Patched version of WaitForMessage that shows a prompt when waiting for human input."""
    messages = []
    while not self.inboxes[source_agent_id].empty():
        message = self.inboxes[source_agent_id].get_nowait()
        if message == EOM:
            break
        messages.append(message)

    if not messages:
        # Show User prompt only when waiting for a human message and the queue is empty
        if source_agent_id == "human":
            # Simple user prompt (not in a panel)
            console.print()  # Add a newline for spacing
            user_input = await asyncio.to_thread(
                console.input, "[bold yellow]User:[/bold yellow] "
            )

            messages.append(user_input)
        else:
            # Wait for input
            messages.append(await self.inboxes[source_agent_id].get())

    for message in messages:
        self.state.session_log.append(
            f"Received message from {source_agent_id}: {message}"
        )
    return "\n".join(messages)


async def handle_user_input(playbooks):
    """Handle user input and send it to the AI agent."""
    while True:
        # User input is now handled in patched_wait_for_message
        # Just check if we need to exit
        if len(playbooks.program.agents) == 0:
            console.print("[yellow]No agents available. Exiting...[/yellow]")
            break

        # Small delay to prevent CPU spinning
        await asyncio.sleep(0.1)


async def main(
    program_paths: str,
    verbose: bool,
    debug: bool = False,
    debug_host: str = "127.0.0.1",
    debug_port: int = 7529,
    wait_for_client: bool = False,
    stop_on_entry: bool = False,
):
    """Main entrypoint for the CLI application.

    Args:
        program_paths: Path to the playbook file(s) to load
        verbose: Whether to print the session log
        debug: Whether to start the debug server
        debug_host: Host address for the debug server
        debug_port: Port for the debug server
        wait_for_client: Whether to wait for a client to connect before starting
        stop_on_entry: Whether to stop at the beginning of playbook execution
    """
    # print(
    #     f"[DEBUG] agent_chat.main called with stop_on_entry={stop_on_entry}, debug={debug}"
    # )

    # Patch the WaitForMessage method before loading agents
    AgentCommunicationMixin.WaitForMessage = patched_wait_for_message

    console.print(f"[green]Loading playbooks from:[/green] {program_paths}")

    session_id = str(uuid.uuid4())
    if isinstance(program_paths, str):
        program_paths = [program_paths]
    playbooks = Playbooks(program_paths, session_id=session_id)
    pubsub = PubSub()

    # Wrap the session_log with the custom wrapper for all agents
    for agent in playbooks.program.agents:
        if hasattr(agent, "state") and hasattr(agent.state, "session_log"):
            agent.state.session_log = SessionLogWrapper(
                agent.state.session_log, pubsub, verbose, agent
            )

    def log_event(event: Event):
        print(event)

    # Start debug server if requested
    if debug:
        console.print(
            f"[green]Starting debug server on {debug_host}:{debug_port}[/green]"
        )
        await playbooks.program.start_debug_server(host=debug_host, port=debug_port)

        # If wait_for_client is True, pause until a client connects
        if wait_for_client:
            console.print(
                f"[yellow]Waiting for a debug client to connect at {debug_host}:{debug_port}...[/yellow]"
            )
            # Wait for a client to connect using the debug server's wait_for_client method
            await playbooks.program._debug_server.wait_for_client()
            console.print("[green]Debug client connected.[/green]")

        # Set stop_on_entry flag in debug server
        if stop_on_entry:
            # print(
            #     "[DEBUG] agent_chat.main - stop_on_entry=True, setting up debug server"
            # )
            # print("[DEBUG] agent_chat.main - clearing _continue_event")
            playbooks.program._debug_server._continue_event.clear()
            # print("[DEBUG] agent_chat.main - calling set_stop_on_entry(True)")
            playbooks.program._debug_server.set_stop_on_entry(True)
            # print("[DEBUG] agent_chat.main - stop_on_entry setup complete")
        else:
            # print("[DEBUG] agent_chat.main - stop_on_entry=False, no special setup")
            pass

    # Start the program
    try:
        if verbose:
            playbooks.event_bus.subscribe("*", log_event)
        await asyncio.gather(playbooks.program.begin(), handle_user_input(playbooks))
    except ExecutionFinished:
        console.print("[green]Execution finished. Exiting...[/green]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting...[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise
    finally:
        if verbose:
            playbooks.event_bus.unsubscribe("*", log_event)
        # Shutdown debug server if it was started
        if debug and playbooks.program._debug_server:
            await playbooks.program.shutdown_debug_server()
        # Restore the original method when we're done
        AgentCommunicationMixin.WaitForMessage = original_wait_for_message


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the agent chat application.")
    parser.add_argument(
        "program_paths",
        help="Paths to the playbook file(s) to load",
        nargs="+",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print the session log"
    )
    parser.add_argument("--debug", action="store_true", help="Start the debug server")
    parser.add_argument(
        "--debug-host",
        default="127.0.0.1",
        help="Debug server host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--debug-port", type=int, default=7529, help="Debug server port (default: 7529)"
    )
    parser.add_argument(
        "--wait-for-client",
        action="store_true",
        help="Wait for a debug client to connect before starting execution",
    )
    parser.add_argument(
        "--skip-compilation",
        action="store_true",
        help="Skip compilation (useful for .pbc files)",
    )
    parser.add_argument(
        "--stop-on-entry",
        action="store_true",
        help="Stop at the beginning of playbook execution",
    )
    args = parser.parse_args()

    try:
        asyncio.run(
            main(
                args.program_paths,
                args.verbose,
                args.debug,
                args.debug_host,
                args.debug_port,
                args.wait_for_client,
                args.stop_on_entry,
            )
        )
    except KeyboardInterrupt:
        print("\nGracefully shutting down...")
