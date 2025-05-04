#!/usr/bin/env python
"""
CLI application for interactive agent chat using playbooks.
Provides a simple terminal interface for communicating with AI agents.
"""
import argparse
import asyncio
import functools
import glob
import sys
from pathlib import Path
from typing import Callable, List

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from playbooks import Playbooks
from playbooks.base_agent import AgentCommunicationMixin
from playbooks.constants import EOM
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


async def main(glob_path: str, verbose: bool):
    """Main entrypoint for the CLI application.

    Args:
        glob_path: Path to the playbook file(s) to load
        verbose: Whether to print the session log
    """
    # Patch the WaitForMessage method before loading agents
    AgentCommunicationMixin.WaitForMessage = patched_wait_for_message

    # Expand glob patterns to file paths
    file_paths = glob.glob(glob_path)
    if not file_paths:
        console.print(
            f"[bold red]Error:[/bold red] No files found matching pattern: {glob_path}"
        )
        sys.exit(1)

    console.print(f"[green]Loading playbooks from:[/green] {file_paths}")
    playbooks = Playbooks(file_paths)
    pubsub = PubSub()

    # Wrap the session_log with the custom wrapper for all agents
    for agent in playbooks.program.agents:
        if hasattr(agent, "state") and hasattr(agent.state, "session_log"):
            agent.state.session_log = SessionLogWrapper(
                agent.state.session_log, pubsub, verbose, agent
            )

    # Start the program
    try:
        await asyncio.gather(playbooks.program.begin(), handle_user_input(playbooks))
    except ExecutionFinished:
        console.print("[green]Execution finished. Exiting...[/green]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting...[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise
    finally:
        # Restore the original method when we're done
        AgentCommunicationMixin.WaitForMessage = original_wait_for_message


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the agent chat application.")
    parser.add_argument("glob_path", help="Path to the playbook file(s) to load")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print the session log"
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(args.glob_path, args.verbose))
    except KeyboardInterrupt:
        print("\nGracefully shutting down...")
