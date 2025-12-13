#!/usr/bin/env python
"""CLI utility application for non-interactive playbook execution.

Provides a mode for running playbooks as command-line utilities with clean
stdout output, automatic argument handling, and semantic stdin support.
"""

import sys
from typing import Any, Dict, List

from rich.console import Console

from playbooks import Playbooks
from playbooks.agents.ai_agent import AIAgent
from playbooks.applications.streaming_observer import ChannelStreamObserver
from playbooks.core.constants import EXECUTION_FINISHED
from playbooks.core.exceptions import ExecutionFinished, InteractiveInputRequired
from playbooks.infrastructure.user_output import user_output
from playbooks.llm.messages import AgentCommunicationLLMMessage
from playbooks.utils.error_utils import check_playbooks_health

console = Console(stderr=True)  # All CLI utility diagnostics to stderr


class CLIStreamObserver(ChannelStreamObserver):
    """Stream observer that outputs clean messages to stdout."""

    def __init__(
        self,
        program,
        stream_enabled: bool = True,
        target_human_id: str = None,
        quiet: bool = False,
    ):
        super().__init__(program, stream_enabled, target_human_id)
        self.quiet = quiet
        self.active_streams = {}  # Track active streams for chunked output

    async def _display_start(self, event, agent_name: str) -> None:
        """Display stream start - prefix to stderr unless quiet."""
        # Track active stream
        self.active_streams[event.stream_id] = {
            "agent_klass": agent_name,
            "sender_id": event.sender_id,
            "recipient_id": event.recipient_id,
            "recipient_klass": event.recipient_klass,
            "content": "",
        }

        if not self.quiet:
            # Show prefix to stderr
            sender_display = (
                f"{agent_name}({event.sender_id})"
                if event.sender_id != "human"
                else agent_name
            )

            if event.recipient_id and event.recipient_klass:
                recipient_display = (
                    f"{event.recipient_klass}({event.recipient_id})"
                    if event.recipient_id != "human"
                    else event.recipient_klass
                )
                print(f"\n[{sender_display} → {recipient_display}]", file=sys.stderr)
            else:
                print(f"\n[{sender_display}]", file=sys.stderr)

    async def _display_chunk(self, event) -> None:
        """Display stream chunk - content to stdout."""
        sys.stdout.write(event.chunk)
        sys.stdout.flush()

    async def _display_complete(self, event) -> None:
        """Display stream completion."""
        print(file=sys.stdout)  # Newline after content

        if event.stream_id in self.active_streams:
            del self.active_streams[event.stream_id]

    async def _display_buffered(self, event) -> None:
        """Display buffered complete message (non-streaming mode)."""
        content = event.final_message.content

        if not self.quiet:
            # Prefix to stderr
            sender_klass = event.final_message.sender_klass or "Agent"
            sender_id = (
                event.final_message.sender_id.id
                if event.final_message.sender_id
                else "unknown"
            )
            sender_display = (
                f"{sender_klass}({sender_id})" if sender_id != "human" else sender_klass
            )

            if event.final_message.recipient_id and event.final_message.recipient_klass:
                recipient_klass = event.final_message.recipient_klass
                recipient_id = event.final_message.recipient_id.id
                recipient_display = (
                    f"{recipient_klass}({recipient_id})"
                    if recipient_id != "human"
                    else recipient_klass
                )
                print(f"\n[{sender_display} → {recipient_display}]", file=sys.stderr)
            else:
                print(f"\n[{sender_display}]", file=sys.stderr)

        # Content to stdout
        print(content, file=sys.stdout)


async def main(
    program_paths: List[str],
    cli_args: Dict[str, Any] = None,
    message: str = None,
    stdin_content: str = None,
    non_interactive: bool = False,
    quiet: bool = False,
    stream: bool = True,
    verbose: bool = False,
    snoop: bool = False,
    **kwargs,
) -> int:
    """Run a playbook as a CLI utility.

    Args:
        program_paths: Paths to playbook files
        cli_args: Parsed CLI arguments to pass to BGN playbook
        message: Natural language message to inject
        stdin_content: Content from stdin if piped
        non_interactive: If True, fail when interactive input is needed
        quiet: If True, suppress all output except agent messages
        stream: Whether to stream output
        verbose: Whether to print verbose logs
        snoop: Whether to display agent-to-agent messages
        **kwargs: Additional arguments for agent_chat compatibility

    Returns:
        Exit code (0=success, 1=error, 3=interactive input required)
    """
    # Quiet mode overrides verbose
    if quiet:
        verbose = False

    # Initialize playbooks with CLI args
    try:
        playbooks = Playbooks(
            program_paths,
            cli_args=cli_args or {},
        )
        await playbooks.initialize()
    except Exception as e:
        console.print(f"[red]Error loading playbooks:[/red] {e}", file=sys.stderr)
        return 1

    # Enable agent streaming if snoop mode is on
    playbooks.program.enable_agent_streaming = snoop

    # Set $startup_message from stdin content only
    # Will auto-promote to Artifact if > threshold (500 chars)
    if stdin_content:
        from playbooks.config import config
        from playbooks.state.variables import Artifact

        for agent in playbooks.program.agents:
            if hasattr(agent, "state"):
                # Check if should be an Artifact based on length threshold
                if len(str(stdin_content)) > config.artifact_result_threshold:
                    # Create Artifact for large content
                    artifact = Artifact(
                        name="startup_message",
                        summary="Startup message from stdin",
                        value=stdin_content,
                    )
                    agent.state.startup_message = artifact
                else:
                    # Regular variable for small content
                    agent.state.startup_message = stdin_content

                # Reset last_sent_state to ensure this variable is included in first I-frame
                agent.state.last_sent_state = None
                agent.state.last_i_frame_execution_id = None

    # Add --message directly to LLM context so it's visible during BGN playbook execution
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

    # Set up CLI stream observer
    stream_observer = CLIStreamObserver(
        playbooks.program,
        stream_enabled=stream,
        quiet=quiet,
    )
    await stream_observer.subscribe_to_all_channels()

    # Patch WaitForMessage to fail in non-interactive mode
    original_wait_for_message = None
    if non_interactive:
        from playbooks.agents.messaging_mixin import MessagingMixin

        original_wait_for_message = MessagingMixin.WaitForMessage

        async def patched_wait(self, source_agent_id: str, *, timeout: float = None):
            if source_agent_id in ("human", "user"):
                raise InteractiveInputRequired(
                    "Interactive input required but --non-interactive mode is enabled"
                )
            return await original_wait_for_message(
                self, source_agent_id, timeout=timeout
            )

        MessagingMixin.WaitForMessage = patched_wait

    # Start the program
    exit_code = 0
    try:
        await playbooks.program.run_till_exit()

    except InteractiveInputRequired as e:
        console.print(f"[red]Error:[/red] {e}", file=sys.stderr)
        exit_code = 3
    except ExecutionFinished:
        if verbose:
            user_output.success(f"{EXECUTION_FINISHED}. Exiting...")
        # Check for errors even on ExecutionFinished
        if playbooks.has_agent_errors():
            exit_code = 1
    except KeyboardInterrupt:
        if verbose:
            user_output.info("Interrupted by user")
        exit_code = 130  # Standard Unix SIGINT exit code
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}", file=sys.stderr)
        exit_code = 1
    finally:
        # Restore the original WaitForMessage if it was patched
        if original_wait_for_message is not None:
            from playbooks.agents.messaging_mixin import MessagingMixin

            MessagingMixin.WaitForMessage = original_wait_for_message

        # Check agent errors for InteractiveInputRequired exceptions
        # These should return exit code 3 even if caught as other exceptions
        agent_errors = playbooks.get_agent_errors()
        for error_info in agent_errors:
            error_obj = error_info.get("error_obj")
            # Check if the error is or contains InteractiveInputRequired
            if isinstance(error_obj, InteractiveInputRequired):
                exit_code = 3
                break
            # Also check if it's a StreamingExecutionError wrapping InteractiveInputRequired
            if hasattr(error_obj, "original_error"):
                if isinstance(error_obj.original_error, InteractiveInputRequired):
                    exit_code = 3
                    break

        # Check for agent errors (only print to stderr if not quiet)
        health_check = check_playbooks_health(
            playbooks,
            print_errors=(not quiet),
            log_errors=True,
            raise_on_errors=False,
            context="cli_utility_execution",
        )
        # Only set exit code to 1 if there are actual errors and no higher exit code already set
        if health_check and health_check.get("has_errors") and exit_code not in (3,):
            exit_code = 1

    return exit_code
