#!/usr/bin/env python
"""CLI application for interactive agent chat using playbooks.

Provides a simple terminal interface for communicating with AI agents.
"""

import argparse
import asyncio
import functools
import os
import select
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, List

# Platform-specific imports for stdin clearing
try:
    import termios
except ImportError:
    termios = None

try:
    if os.name == "nt":
        import msvcrt
    else:
        msvcrt = None
except ImportError:
    msvcrt = None

import litellm
from rich.console import Console

from playbooks import Playbooks
from playbooks.agents.messaging_mixin import MessagingMixin
from playbooks.applications.streaming_observer import (
    ChannelStreamObserver as BaseChannelStreamObserver,
)
from playbooks.channels.stream_events import (
    StreamChunkEvent,
    StreamCompleteEvent,
    StreamStartEvent,
)
from playbooks.constants import EOM, EXECUTION_FINISHED
from playbooks.debug_logger import debug
from playbooks.events import Event
from playbooks.exceptions import ExecutionFinished
from playbooks.meetings.meeting_manager import MeetingManager
from playbooks.message import MessageType
from playbooks.program import Program
from playbooks.user_output import user_output
from playbooks.utils.error_utils import check_playbooks_health

# Add the src directory to the Python path to import playbooks
sys.path.insert(0, str(Path(__file__).parent.parent))

# Initialize Rich console
console = Console()


def clear_stdin():
    """Clear any pending input from stdin buffer.

    This prevents pre-filled input when prompting the user.
    Uses platform-specific methods for optimal clearing.
    """
    try:
        if os.name == "nt" and msvcrt is not None:  # Windows
            # Clear Windows console input buffer
            while msvcrt.kbhit():
                msvcrt.getch()
        else:  # Unix/Linux/macOS
            # Use termios for aggressive clearing if available
            if termios is not None:
                try:
                    termios.tcflush(sys.stdin, termios.TCIFLUSH)
                    return  # Success, no need for fallback
                except (OSError, AttributeError):
                    pass  # Fall through to select-based approach

            # Fallback: use select to check and clear available input
            if hasattr(select, "select"):
                # Check if there's input available without blocking
                if select.select([sys.stdin], [], [], 0.0)[0]:
                    # Read and discard available input
                    try:
                        while select.select([sys.stdin], [], [], 0.0)[0]:
                            sys.stdin.read(1)
                    except (OSError, IOError):
                        pass

    except Exception:
        # Ignore all errors - stdin clearing is a best-effort operation
        pass


class PubSub:
    """Simple publish-subscribe mechanism for event handling."""

    def __init__(self) -> None:
        self.subscribers: List[Callable] = []

    def subscribe(self, callback: Callable) -> None:
        """Subscribe a callback function to receive messages."""
        self.subscribers.append(callback)

    def publish(self, message: Any) -> None:
        """Publish a message to all subscribers."""
        for subscriber in self.subscribers:
            subscriber(message)


class ChannelStreamObserver(BaseChannelStreamObserver):
    """Terminal-based streaming observer - displays agent messages in the console."""

    def __init__(
        self,
        program: Program,
        stream_enabled: bool = True,
        target_human_id: str = None,
    ):
        super().__init__(program, stream_enabled, target_human_id)
        self.active_streams = {}  # stream_id -> {"agent_klass": str, "content": str}

    async def _display_start(self, event: StreamStartEvent, agent_name: str) -> None:
        """Display stream start in terminal."""
        self.active_streams[event.stream_id] = {
            "agent_klass": agent_name,
            "content": "",
        }
        # Show recipient if available (for multi-human scenarios)
        if event.recipient_id and event.recipient_klass:
            console.print(
                f"\n[green]{agent_name}[/green] → [yellow]{event.recipient_klass}({event.recipient_id})[/yellow]: ",
                end="",
            )
        else:
            console.print(f"\n[green]{agent_name}:[/green] ", end="")

    async def _display_chunk(self, event: StreamChunkEvent) -> None:
        """Display stream chunk in terminal."""
        if event.stream_id in self.active_streams:
            self.active_streams[event.stream_id]["content"] += event.chunk
        print(event.chunk, end="", flush=True)

    async def _display_complete(self, event: StreamCompleteEvent) -> None:
        """Display stream completion in terminal."""
        console.print()  # Newline to finish streaming
        if event.stream_id in self.active_streams:
            del self.active_streams[event.stream_id]

    async def _display_buffered(self, event: StreamCompleteEvent) -> None:
        """Display buffered complete message in terminal (non-streaming mode)."""
        # Get agent name from active streams or event
        agent_name = "Agent"
        if event.stream_id in self.active_streams:
            stream_data = self.active_streams[event.stream_id]
            agent_name = stream_data["agent_klass"]
            content = event.final_message.content or stream_data["content"]
            del self.active_streams[event.stream_id]
        else:
            content = event.final_message.content

        console.print(f"\n[green]{agent_name}:[/green] {content}")


class SessionLogWrapper:
    """Wrapper around session_log that publishes updates."""

    def __init__(self, session_log: Any, pubsub: PubSub, verbose: bool = False) -> None:
        self._session_log = session_log
        self._pubsub = pubsub
        self.verbose = verbose

    def append(self, msg: str) -> None:
        """Append a message to the session log and publish it."""
        self._session_log.append(msg)

        if self.verbose:
            self._pubsub.publish(str(msg))

    def __iter__(self):
        return iter(self._session_log)

    def __str__(self) -> str:
        return str(self._session_log)


# Store original methods for restoring later
original_wait_for_message = MessagingMixin.WaitForMessage
original_broadcast_to_meeting = None  # Will be set after MeetingManager is imported
original_route_message = None  # Will be set after Program is loaded


@functools.wraps(original_wait_for_message)
async def patched_wait_for_message(self, source_agent_id: str):
    """Patched version of WaitForMessage that shows a prompt when waiting for human input."""
    # For human input, show a prompt before calling the normal WaitForMessage
    # Accept both "human" and "user" as identifiers for human input
    if source_agent_id in ("human", "user"):
        # Check if there are already messages waiting using queue peek
        human_message = await self._message_queue.peek(
            lambda msg: msg.sender_id.id == "human"
        )

        if not human_message:
            # No human messages waiting, show prompt
            console.print()  # Add a newline for spacing
            # Clear stdin buffer to prevent pre-filled input
            await asyncio.to_thread(clear_stdin)

            # Determine which humans exist in the program
            program: Program = self.program
            humans = [
                a
                for a in program.agents
                if a.klass.endswith("Human") or a.id == "human"
            ]

            # If multiple humans, let user specify which one is speaking
            if len(humans) > 1:
                console.print(
                    f"[dim]Available humans: {', '.join(h.klass for h in humans)}[/dim]"
                )
                console.print(
                    "[dim]Format: HumanName: your message  (e.g., 'Alice: Hello')[/dim]"
                )
                user_input = await asyncio.to_thread(
                    console.input, "[bold yellow]Input:[/bold yellow] "
                )

                # Parse "HumanName: message" format
                sender_id = "human"
                sender_klass = "human"
                message_content = user_input

                if ": " in user_input:
                    potential_human_name, rest = user_input.split(": ", 1)
                    # Check if potential_human_name matches any human
                    matching_human = next(
                        (
                            h
                            for h in humans
                            if h.klass.lower() == potential_human_name.lower()
                        ),
                        None,
                    )
                    if matching_human:
                        sender_id = matching_human.id
                        sender_klass = matching_human.klass
                        message_content = rest
                    # If no match, treat entire input as message from default "human"
            else:
                # Single human, use simple prompt
                user_input = await asyncio.to_thread(
                    console.input, "[bold yellow]User:[/bold yellow] "
                )
                sender_id = "human"
                sender_klass = "human"
                message_content = user_input

            # Send the user input and EOM
            for message in [message_content, EOM]:
                await program.route_message(
                    sender_id=sender_id,
                    sender_klass=sender_klass,
                    receiver_spec=f"agent {self.id}",
                    message=message,
                )

    # Call the normal WaitForMessage which handles message delivery
    return await original_wait_for_message(self, source_agent_id)


async def patched_broadcast_to_meeting_as_owner(
    self,
    meeting_id: str,
    message: str,
    from_agent_id: str = None,
    from_agent_klass: str = None,
):
    """Patched version of broadcast_to_meeting_as_owner that displays meeting messages nicely."""
    # Display the meeting message with formatting
    if not from_agent_id or not from_agent_klass:
        from_agent_id = self.agent.id
        from_agent_klass = self.agent.klass

    # Format and display the meeting broadcast
    console.print(
        f"\n[bold blue]📢 Meeting {meeting_id}[/bold blue] - [cyan]{from_agent_klass}({from_agent_id})[/cyan]: {message}"
    )

    # Call the original method
    if original_broadcast_to_meeting:
        return await original_broadcast_to_meeting(
            self, meeting_id, message, from_agent_id, from_agent_klass
        )


async def patched_route_message(
    self,
    sender_id: str,
    sender_klass: str,
    receiver_spec: str,
    message: str,
    message_type=MessageType.DIRECT,
    meeting_id: str = None,
):
    """Patched version of route_message that displays agent-to-agent messages."""
    # Extract receiver info
    from playbooks.identifiers import AgentID

    debug(
        "Patched route message",
        sender_id=sender_id,
        receiver_spec=receiver_spec,
        message=message[:50],
    )

    recipient_agent_id = AgentID.parse(receiver_spec)
    recipient_id = recipient_agent_id.id

    recipient = self.agents_by_id.get(recipient_id)
    recipient_klass = recipient.klass if recipient else "Unknown"

    # Display agent-to-agent message with formatting
    if message != EOM:
        console.print(
            f"\n[bold magenta]💬 Message[/bold magenta]: [purple]{sender_klass}({sender_id})[/purple] → [purple]{recipient_klass}({recipient_id})[/purple]: {message}"
        )

    # Call the original method
    if original_route_message:
        return await original_route_message(
            self,
            sender_id,
            sender_klass,
            receiver_spec,
            message,
            message_type,
            meeting_id,
        )


async def main(
    program_paths: str,
    verbose: bool,
    enable_debug: bool = False,
    debug_host: str = "127.0.0.1",
    debug_port: int = 7529,
    wait_for_client: bool = False,
    stop_on_entry: bool = False,
    stream: bool = True,
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
        enable_debug: Whether to start the debug server
        debug_host: Host address for the debug server
        debug_port: Port for the debug server
        wait_for_client: Whether to wait for a client to connect before starting
        stop_on_entry: Whether to stop at the beginning of playbook execution
        stream: Whether to stream the output

    """
    #     f"[DEBUG] agent_chat.main called with stop_on_entry={stop_on_entry}, debug={debug}"
    # )

    # Patch the WaitForMessage method before loading agents
    MessagingMixin.WaitForMessage = patched_wait_for_message

    user_output.info(f"Loading playbooks from: {program_paths}")

    session_id = str(uuid.uuid4())
    if isinstance(program_paths, str):
        program_paths = [program_paths]
    try:
        playbooks = Playbooks(program_paths, session_id=session_id)
        await playbooks.initialize()
    except litellm.exceptions.AuthenticationError as e:
        user_output.error("Authentication error", details=str(e))
        raise

    # Store original methods and apply patches after playbooks are loaded
    global original_broadcast_to_meeting, original_route_message
    original_broadcast_to_meeting = MeetingManager.broadcast_to_meeting_as_owner
    original_route_message = Program.route_message

    # Apply patches
    MeetingManager.broadcast_to_meeting_as_owner = patched_broadcast_to_meeting_as_owner
    if not stream:
        Program.route_message = patched_route_message

    pubsub = PubSub()

    # Set up channel stream observer for displaying agent messages
    stream_observer = ChannelStreamObserver(playbooks.program, stream_enabled=stream)

    # Subscribe to existing channels
    # The observer automatically subscribes to ChannelCreatedEvent via EventBus
    await stream_observer.subscribe_to_all_channels()

    # Wrap session logs with SessionLogWrapper for verbose output
    for agent in playbooks.program.agents:
        if hasattr(agent, "state") and hasattr(agent.state, "session_log"):
            wrapper = SessionLogWrapper(agent.state.session_log, pubsub, verbose)
            agent.state.session_log = wrapper

    def log_event(event: Event) -> None:
        print(event)

    # Connect to debug adapter if requested
    if enable_debug:
        # Start debug server with stop-on-entry flag
        debug(f"Starting debug server with agents: {playbooks.program.agents}")
        await playbooks.program.start_debug_server(
            host=debug_host, port=debug_port, stop_on_entry=stop_on_entry
        )

        # If wait_for_client is True, wait for debug adapter to connect
        if wait_for_client:
            console.print(
                f"[yellow]Waiting for debug client to connect at {debug_host}:{debug_port}...[/yellow]"
            )
            await playbooks.program._debug_server.wait_for_client()
            console.print("[green]Debug client connected.[/green]")

    # Start the program
    try:
        if verbose:
            playbooks.event_bus.subscribe("*", log_event)
        await playbooks.program.run_till_exit()
    except ExecutionFinished:
        user_output.success(f"{EXECUTION_FINISHED}. Exiting...")
    except KeyboardInterrupt:
        user_output.info("Exiting...")
    except Exception as e:
        user_output.error("Execution error", details=str(e))
        raise
    finally:
        # Check for agent errors after execution using standardized error handling
        check_playbooks_health(
            playbooks,
            print_errors=True,
            log_errors=True,
            raise_on_errors=False,  # Don't raise in CLI context
            context="agent_chat_execution",
        )
        if verbose:
            playbooks.event_bus.unsubscribe("*", log_event)
        # Shutdown debug server if it was started
        if enable_debug and playbooks.program._debug_server:
            await playbooks.program.shutdown_debug_server()
        # Restore the original methods when we're done
        MessagingMixin.WaitForMessage = original_wait_for_message
        if original_broadcast_to_meeting:
            MeetingManager.broadcast_to_meeting_as_owner = original_broadcast_to_meeting
        if original_route_message:
            Program.route_message = original_route_message


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
    parser.add_argument(
        "--stream",
        type=lambda x: x.lower() in ["true", "1", "yes"],
        default=True,
        help="Enable/disable streaming output (default: True). Use --stream=False for buffered output",
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
                args.stream,
            )
        )
    except KeyboardInterrupt:
        print("\nGracefully shutting down...")
