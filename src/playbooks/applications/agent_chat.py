#!/usr/bin/env python
"""CLI application for interactive agent chat using playbooks.

Provides a simple terminal interface for communicating with AI agents.
"""

import argparse
import asyncio
import os
import select
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

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
from playbooks.agents.ai_agent import AIAgent
from playbooks.agents.messaging_mixin import MessagingMixin
from playbooks.applications.human_wait import build_human_wait_patch
from playbooks.applications.streaming_observer import (
    ChannelStreamObserver as BaseChannelStreamObserver,
)
from playbooks.channels.stream_events import (
    StreamChunkEvent,
    StreamCompleteEvent,
    StreamStartEvent,
)
from playbooks.core.constants import EOM, EXECUTION_FINISHED
from playbooks.core.events import Event, MessageRoutedEvent
from playbooks.core.exceptions import ExecutionFinished
from playbooks.core.identifiers import AgentID
from playbooks.core.message import MessageType
from playbooks.infrastructure.logging.debug_logger import debug
from playbooks.infrastructure.user_output import user_output
from playbooks.llm.messages import AgentCommunicationLLMMessage
from playbooks.program import Program
from playbooks.utils.error_utils import check_playbooks_health

# Add the src directory to the Python path to import playbooks
sys.path.insert(0, str(Path(__file__).parent.parent))

# Initialize Rich console - use stderr for all diagnostics
console = console_stderr = Console(stderr=True)
# Separate console for stdout (for colored message headers)
console_stdout = Console(stderr=False)


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

    @staticmethod
    def _format_agent_display(klass: str, agent_id: str) -> str:
        """Format agent display string.

        Human agents show as just their klass name (e.g., "User").
        AI agents show as klass(id) (e.g., "Assistant(1000)").

        Args:
            klass: Agent class name
            agent_id: Agent ID

        Returns:
            Formatted display string
        """
        if agent_id == "human":
            return klass
        return f"{klass}({agent_id})"

    async def on_stream_start(self, event: StreamStartEvent) -> None:
        """Handle stream start - always track stream, display only if streaming."""
        sender = self.program.agents_by_id.get(event.sender_id)
        agent_name = sender.klass if sender else "Agent"

        # Always track the stream (needed for non-streaming mode to work correctly)
        self.active_streams[event.stream_id] = {
            "agent_klass": agent_name,
            "sender_id": event.sender_id,
            "recipient_id": event.recipient_id,
            "recipient_klass": event.recipient_klass,
            "content": "",
        }

        # Call parent to handle display logic (will call _display_start if streaming)
        await super().on_stream_start(event)

    async def _display_start(self, event: StreamStartEvent, agent_name: str) -> None:
        """Display stream start - prefix to stderr, content to stdout."""
        sender_display = self._format_agent_display(agent_name, event.sender_id)

        if event.recipient_id and event.recipient_klass:
            recipient_display = self._format_agent_display(
                event.recipient_klass, event.recipient_id
            )
            # Prefix to stdout in bracket format with color
            console_stderr.print(
                f"\n[cyan][{sender_display} → {recipient_display}][/cyan]"
            )
        else:
            console_stderr.print(f"\n[cyan][{sender_display}][/cyan]")

    async def _display_chunk(self, event: StreamChunkEvent) -> None:
        """Display stream chunk - content to stdout."""
        if event.stream_id in self.active_streams:
            self.active_streams[event.stream_id]["content"] += event.chunk
        # Content to stdout
        sys.stdout.write(event.chunk)
        sys.stdout.flush()

    async def _display_complete(self, event: StreamCompleteEvent) -> None:
        """Display stream completion."""
        print(file=sys.stdout)  # Newline to finish content
        if event.stream_id in self.active_streams:
            del self.active_streams[event.stream_id]

    async def _display_buffered(self, event: StreamCompleteEvent) -> None:
        """Display buffered complete message (non-streaming mode)."""
        # Get sender/recipient info from active streams or event
        if event.stream_id in self.active_streams:
            stream_data = self.active_streams[event.stream_id]
            sender_klass = stream_data["agent_klass"]
            sender_id = stream_data["sender_id"]
            recipient_id = stream_data.get("recipient_id")
            recipient_klass = stream_data.get("recipient_klass")
            content = event.final_message.content or stream_data["content"]
            del self.active_streams[event.stream_id]
        else:
            # Fallback to extracting from event
            sender_klass = event.final_message.sender_klass or "Agent"
            sender_id = (
                event.final_message.sender_id.id
                if event.final_message.sender_id
                else "unknown"
            )
            recipient_id = (
                event.final_message.recipient_id.id
                if event.final_message.recipient_id
                else None
            )
            recipient_klass = event.final_message.recipient_klass
            content = event.final_message.content

        # Prefix to stdout, content to stdout
        sender_display = self._format_agent_display(sender_klass, sender_id)

        if recipient_id and recipient_klass:
            recipient_display = self._format_agent_display(
                recipient_klass, recipient_id
            )
            console_stderr.print(
                f"\n[cyan][{sender_display} → {recipient_display}][/cyan]"
            )
        else:
            console_stderr.print(f"\n[cyan][{sender_display}][/cyan]")

        # Content to stdout
        print(content, file=sys.stdout)
        sys.stdout.flush()  # Ensure content is displayed immediately


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
original_broadcast_to_meeting = None  # deprecated (no longer used)
original_broadcast_to_meeting_participant = None  # deprecated (no longer used)


def _on_message_routed(event: MessageRoutedEvent) -> None:
    """Display meeting broadcasts in CLI without patching meeting manager methods."""
    msg = event.message
    if not msg:
        return
    try:
        if (
            getattr(msg, "message_type", None)
            and msg.message_type == MessageType.MEETING_BROADCAST
        ):
            meeting_id = (
                msg.meeting_id.id if getattr(msg, "meeting_id", None) else "unknown"
            )
            console.print(
                f"\n[bold blue]📢 meeting {meeting_id}[/bold blue] - "
                f"[cyan]{msg.sender_klass}({msg.sender_id.id})[/cyan]: {msg.content}"
            )
    except Exception:
        # Best-effort only; never break execution
        return


async def prompt_for_human_input(agent_self):
    """Prompt in CLI and enqueue a human message for the waiting agent."""
    console.print()  # Add a newline for spacing
    await asyncio.to_thread(clear_stdin)

    program: Program = agent_self.program
    humans = [a for a in program.agents if a.klass.endswith("Human") or a.id == "human"]

    sender_id = "human"
    sender_klass = "human"
    message_content = ""

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

        message_content = user_input
        if ": " in user_input:
            potential_human_name, rest = user_input.split(": ", 1)
            matching_human = next(
                (h for h in humans if h.klass.lower() == potential_human_name.lower()),
                None,
            )
            if matching_human:
                sender_id = matching_human.id
                sender_klass = matching_human.klass
                message_content = rest
    else:
        message_content = await asyncio.to_thread(
            console.input, "[bold yellow]User:[/bold yellow] "
        )

    for message in [message_content, EOM]:
        await program.route_message(
            sender_id=sender_id,
            sender_klass=sender_klass,
            receiver_spec=str(AgentID.parse(agent_self.id)),
            message=message,
        )


async def patched_broadcast_to_meeting_as_owner(*args, **kwargs):
    raise RuntimeError(
        "broadcast_to_meeting_as_owner no longer exists; use Program.route_message"
    )


async def patched_broadcast_to_meeting_as_participant(*args, **kwargs):
    raise RuntimeError(
        "broadcast_to_meeting_as_participant no longer exists; use Program.route_message"
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
    snoop: bool = False,
    initial_state: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
) -> None:
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
        snoop: Whether to display agent-to-agent messages
        initial_state: Optional initial state variables to set on agents
        message: Optional message to send from human to first AI agent after initialization

    """
    #     f"[DEBUG] agent_chat.main called with stop_on_entry={stop_on_entry}, debug={debug}"
    # )

    # Patch the WaitForMessage method before loading agents
    MessagingMixin.WaitForMessage = build_human_wait_patch(
        original_wait_for_message,
        on_prompt=prompt_for_human_input,
    )

    user_output.info(f"Loading playbooks from: {program_paths}")

    session_id = str(uuid.uuid4())
    if isinstance(program_paths, str):
        program_paths = [program_paths]
    try:
        playbooks = Playbooks(
            program_paths,
            session_id=session_id,
            initial_state=initial_state or {},
        )
        await playbooks.initialize()
    except litellm.exceptions.AuthenticationError as e:
        user_output.error("Authentication error", details=str(e))
        raise

    # Enable agent streaming if snoop mode is on
    playbooks.program.enable_agent_streaming = snoop

    # Subscribe to routed messages for meeting broadcast display
    playbooks.event_bus.subscribe(MessageRoutedEvent, _on_message_routed)

    pubsub = PubSub()

    # Set up channel stream observer for displaying agent messages
    stream_observer = ChannelStreamObserver(playbooks.program, stream_enabled=stream)

    # Subscribe to existing channels
    # The observer automatically subscribes to ChannelCreatedEvent via EventBus
    await stream_observer.subscribe_to_all_channels()

    # Wrap session logs with SessionLogWrapper for verbose output
    for agent in playbooks.program.agents:
        if (
            isinstance(agent, AIAgent)
            and hasattr(agent, "state")
            and "session_log" in agent.state
        ):
            wrapper = SessionLogWrapper(agent.session_log, pubsub, verbose)
            agent.session_log = wrapper

    # Add message directly to LLM context so it's visible during BGN playbook execution
    if message:
        human = playbooks.program.agents_by_id.get("human")
        human_klass = human.klass if human else "User"

        for agent in playbooks.program.agents:
            if isinstance(agent, AIAgent):
                # Add message to top-level LLM messages so it's visible in BGN playbooks
                agent_comm_msg = AgentCommunicationLLMMessage(
                    f"Received message from {human_klass}(human): {message}",
                    sender_agent=human_klass,
                    target_agent=agent.klass,
                )
                agent.call_stack.top_level_llm_messages.append(agent_comm_msg)

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
        playbooks.event_bus.unsubscribe(MessageRoutedEvent, _on_message_routed)


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
    parser.add_argument(
        "--snoop",
        type=lambda x: x.lower() in ["true", "1", "yes"],
        default=False,
        help="Display messages exchanged between agents (default: False). Use --snoop=true to see all agent-to-agent communication",
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
                args.snoop,
            )
        )
    except KeyboardInterrupt:
        print("\nGracefully shutting down...")
