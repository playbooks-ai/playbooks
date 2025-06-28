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

import litellm
from rich.console import Console

from playbooks import Playbooks
from playbooks.agents import AgentCommunicationMixin
from playbooks.constants import EOM
from playbooks.events import Event
from playbooks.exceptions import ExecutionFinished
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
        self.current_streaming_panel = None
        self.streaming_content = ""
        self.is_streaming = False

    def append(self, msg, level=SessionLogItemLevel.MEDIUM):
        """Append a message to the session log and publish it."""
        self._session_log.append(msg, level)
        # Skip traditional display entirely - streaming handles all output now
        # Traditional panels are disabled in favor of streaming output

        if self.verbose:
            self._pubsub.publish(str(msg))

    def __iter__(self):
        return iter(self._session_log)

    def __str__(self):
        return str(self._session_log)

    async def start_streaming_say(self, recipient=None):
        """Start displaying a streaming Say() message."""
        agent_name = self.agent.klass if self.agent else "Agent"
        self.streaming_content = ""
        self.is_streaming = True

        # Print agent name to show streaming is starting
        console.print(f"\n[green]{agent_name}:[/green] ", end="")

    async def stream_say_update(self, content: str):
        """Add content to the current streaming Say() message."""
        self.streaming_content += content
        # Simple streaming display - just print the new content
        print(content, end="", flush=True)

    async def complete_streaming_say(self):
        """Complete the current streaming Say() message."""
        if self.is_streaming:
            # Print a new line to finish the streaming output
            console.print()

            # Reset streaming state
            self.is_streaming = False
            self.streaming_content = ""


# Store original method for restoring later
original_wait_for_message = AgentCommunicationMixin.WaitForMessage


@functools.wraps(original_wait_for_message)
async def patched_wait_for_message(self, source_agent_id: str):
    """Patched version of WaitForMessage that shows a prompt when waiting for human input."""
    # For human input, show a prompt before calling the normal WaitForMessage
    if source_agent_id == "human":
        # Check if there are already messages waiting
        messages = self.inbox._peek_all_messages()
        human_messages = [msg for msg in messages if msg.sender_id == "human"]

        if not human_messages:
            # No human messages waiting, show prompt
            console.print()  # Add a newline for spacing
            user_input = await asyncio.to_thread(
                console.input, "[bold yellow]User:[/bold yellow] "
            )
            # Send the user input and EOM
            await self.program.route_message("human", self.id, user_input)
            await self.program.route_message("human", self.id, EOM)

    # Call the normal WaitForMessage which handles message delivery
    return await original_wait_for_message(self, source_agent_id)


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
    """
    Playbooks application host for agent chat. You can execute a playbooks program within this application container.

    Example:
        ```sh
        python -m playbooks.applications.agent_chat tests/data/02-personalized-greeting.pb
        ```

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
    try:
        playbooks = Playbooks(program_paths, session_id=session_id)
    except litellm.exceptions.AuthenticationError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise

    pubsub = PubSub()

    # Wrap the session_log with the custom wrapper for all agents
    for agent in playbooks.program.agents:
        if hasattr(agent, "state") and hasattr(agent.state, "session_log"):
            wrapper = SessionLogWrapper(agent.state.session_log, pubsub, verbose, agent)
            agent.state.session_log = wrapper

            # Add streaming methods to the agent if it's not a human agent
            if hasattr(agent, "klass") and agent.klass != "human":
                agent.start_streaming_say = wrapper.start_streaming_say
                agent.stream_say_update = wrapper.stream_say_update
                agent.complete_streaming_say = wrapper.complete_streaming_say

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
        help="Skip compilation (automatically skipped for .pbasm files)",
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
