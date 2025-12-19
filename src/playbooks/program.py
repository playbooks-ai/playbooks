"""Program execution orchestration for playbooks.

This module provides the Program class that orchestrates the execution of
playbooks, manages agent lifecycles, handles event routing, and coordinates
communication between all system components.
"""

import asyncio
import json
import logging
import random
import re
from pathlib import Path

# Removed threading import - using asyncio only
from typing import Any, Dict, List, Optional, Type, Union

from playbooks.compilation.markdown_to_ast import markdown_to_ast
from playbooks.config import config
from playbooks.core.constants import EXECUTION_FINISHED, HUMAN_AGENT_KLASS
from playbooks.core.events import (
    AgentCreatedEvent,
    ChannelCreatedEvent,
    CompiledProgramEvent,
    MessageRoutedEvent,
    MessageSentEvent,
    ProgramTerminatedEvent,
)
from playbooks.core.exceptions import ExecutionFinished, KlassNotFoundError
from playbooks.core.identifiers import AgentID, MeetingID
from playbooks.core.message import Message, MessageType
from playbooks.core.stream_result import StreamResult
from playbooks.infrastructure.event_bus import EventBus
from playbooks.infrastructure.logging.debug_logger import debug
from playbooks.state.variables import Artifact
from playbooks.utils.error_utils import log_agent_errors
from playbooks.utils.langfuse_event_handler import LangfuseEventHandler

from .agents import AIAgent, HumanAgent, RemoteAIAgent
from .agents.agent_builder import AgentBuilder
from .agents.base_agent import BaseAgent
from .channels import AgentParticipant, Channel, HumanParticipant
from .debug.server import (
    DebugServer,  # Note: Actually a debug client that connects to VSCode
)
from .meetings import MeetingRegistry
from .utils import file_utils

logger = logging.getLogger(__name__)


def is_agent_busy(agent: BaseAgent) -> bool:
    """Check if agent is busy, with defensive handling.

    Args:
        agent: Agent instance to check

    Returns:
        True if agent is busy, False otherwise (defaults to False if state is missing)
    """
    if not hasattr(agent, "state"):
        return False
    return getattr(agent.state, "_busy", False)


class AsyncAgentRuntime:
    """Asyncio-based runtime that manages agent execution.

    Uses asyncio tasks instead of threads for concurrent agent execution.
    Manages agent lifecycle, task tracking, and graceful shutdown.

    Attributes:
        program: Reference to the Program instance
        agent_tasks: Dictionary mapping agent IDs to their asyncio tasks
        running_agents: Dictionary tracking which agents are currently running
    """

    def __init__(self, program: "Program") -> None:
        """Initialize the async agent runtime.

        Args:
            program: The Program instance managing this runtime
        """
        self.program = program
        self.agent_tasks: Dict[str, asyncio.Task] = {}
        self.running_agents: Dict[str, bool] = {}

    async def start_agent(self, agent: BaseAgent) -> Optional[asyncio.Task]:
        """Start an agent as an asyncio task.

        Creates an asyncio task for the agent and tracks it. If the agent
        is already running, this is a no-op.

        Args:
            agent: The agent instance to start

        Returns:
            The created asyncio task, or None if agent was already running
        """
        if agent.id in self.running_agents and self.running_agents[agent.id]:
            return

        self.running_agents[agent.id] = True

        # debug("Starting agent", agent_id=agent.id, agent_type=agent.klass)

        task = asyncio.create_task(self._agent_main(agent))
        self.agent_tasks[agent.id] = task
        # Don't await - let it run independently
        return task

    async def stop_agent(self, agent_id: str) -> None:
        """Stop an agent gracefully.

        Signals the agent to stop, cancels its task, and waits for cleanup.
        Handles cancellation errors and notifies the debug server.

        Args:
            agent_id: ID of the agent to stop

        Note:
            Silently handles agents that are not running
        """
        if agent_id not in self.running_agents:
            return

        # debug("Stopping agent", agent_id=agent_id)

        # Signal shutdown
        self.running_agents[agent_id] = False

        # Cancel the task
        if agent_id in self.agent_tasks:
            task = self.agent_tasks[agent_id]
            if not task.done():
                task.cancel()
            # Always await to ensure cleanup, even if task is already done
            try:
                await task
            except (asyncio.CancelledError, RuntimeError):
                # CancelledError: normal cancellation
                # RuntimeError: can occur if task is in an invalid state ("await wasn't used with future")
                pass
            except Exception:
                # Catch any other exceptions during task cleanup to prevent shutdown failures
                pass

        # Notify debug server of agent termination
        if self.program._debug_server:
            await self.program._debug_server.send_thread_exited_event(agent_id)

        # Clean up
        self.agent_tasks.pop(agent_id, None)
        self.running_agents.pop(agent_id, None)

    async def stop_all_agents(self) -> None:
        """Stop all running agents.

        Stops all agents tracked in running_agents, useful for shutdown.
        """
        agent_ids = list(self.running_agents.keys())
        for agent_id in agent_ids:
            await self.stop_agent(agent_id)

    async def _agent_main(self, agent: BaseAgent) -> None:
        """Main coroutine for agent execution.

        Wraps agent.begin() with error handling and cleanup. Catches
        ExecutionFinished exceptions and handles agent errors gracefully.

        Args:
            agent: The agent instance to execute

        Raises:
            ExecutionFinished: Handled internally, signals normal completion
            asyncio.CancelledError: Re-raised for proper cancellation handling
            Exception: Other exceptions are logged and re-raised
        """
        try:
            # Initialize and start the agent
            await agent.initialize()
            if not self.program.execution_finished:
                await agent.begin()

        except ExecutionFinished as e:
            # Signal that execution is finished
            await self.program.set_execution_finished(reason="normal", exit_code=0)
            debug(
                "Agent execution finished",
                agent_id=agent.id,
                agent_name=str(agent),
                reason=str(e),
            )
            # Don't re-raise ExecutionFinished to allow proper cleanup
            return
        except asyncio.CancelledError:
            debug(
                "Agent stopped",
                agent_id=agent.id,
                agent_name=str(agent),
                reason="cancelled",
            )

            raise
        except Exception as e:
            # Use structured logging for production errors (important for monitoring)
            logger.error(
                f"Fatal error in agent {agent.id}: {e}",
                extra={
                    "agent_id": agent.id,
                    "agent_name": str(agent),
                    "error_type": type(e).__name__,
                    "context": "agent_execution",
                },
                exc_info=True,
            )

            # Also use debug for developer troubleshooting
            debug(
                "Fatal agent error",
                agent_id=agent.id,
                agent_name=str(agent),
                error_type=type(e).__name__,
                error=str(e),
            )

            # Store the error on the agent for debugging
            agent._execution_error = e

            # Mark the program as having errors for test visibility
            self.program._has_agent_errors = True

            # Log agent error using error_utils for consistency
            error_info = [
                {
                    "agent_id": agent.id,
                    "agent_name": str(agent),
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "error_obj": e,
                }
            ]
            log_agent_errors(error_info, "agent_runtime")

            # Signal execution finished so run_till_exit doesn't hang
            # This ensures the program terminates even if an agent fails
            await self.program.set_execution_finished(reason="error", exit_code=1)

            raise
        finally:
            # Cleanup agent resources
            if hasattr(agent, "cleanup"):
                await agent.cleanup()

    async def wait_for_all_agents_idle(self) -> None:
        """Wait for all agents to become idle.

        Args:
            self: The Program instance
        """
        done = False
        while not done:
            debug("Waiting for all agents to become idle")
            done = True
            for agent in self.program.agents:
                if isinstance(agent, AIAgent):
                    if len(agent.call_stack.frames) > 0:
                        if is_agent_busy(agent):
                            done = False
                            break
            await asyncio.sleep(1)
        debug("All agents are idle")


class ProgramAgentsCommunicationMixin:
    async def route_message(
        self: "Program",
        sender_id: str,
        sender_klass: str,
        receiver_spec: str,
        message: str,
        message_type: MessageType = MessageType.DIRECT,
        meeting_id: Optional[str] = None,
        stream_id: Optional[str] = None,
    ) -> None:
        """Routes a message to receiver agent(s) via the unified channel architecture.

        Features:
        - Unified interface for all communication types
        - Streaming support (via stream_id)
        - Observable communication
        - Agent targeting in meetings

        Args:
            stream_id: If provided, this message is part of a stream
        """
        # Handle Artifact objects - use value for actual message delivery
        message_str = message
        if isinstance(message, Artifact):
            message_str = str(message.value)

        debug(
            "Routing message via channel",
            sender_id=sender_id,
            receiver_spec=receiver_spec,
            message_type=message_type.value if message_type else None,
            message_length=len(message_str) if message_str else 0,
        )

        # Parse IDs at entry point - convert strings to structured types
        sender_agent_id = AgentID.parse(sender_id)
        parsed_meeting_id = MeetingID.parse(meeting_id) if meeting_id else None

        # Parse target agents from receiver_spec (for meetings with targeting)
        target_agent_ids = None
        if receiver_spec.startswith("meeting "):
            # Check for agent targeting: "meeting X, agent Y, agent Z"
            parts = receiver_spec.split(",")
            if len(parts) > 1:
                # Extract meeting ID from first part
                meeting_spec = parts[0].strip()
                parsed_meeting_id = MeetingID.parse(meeting_spec)
                receiver_spec = (
                    meeting_spec  # Use clean meeting spec for channel lookup
                )

                # Extract target agent IDs from remaining parts
                target_agent_ids = []
                for part in parts[1:]:
                    part = part.strip()
                    if part.startswith("agent "):
                        target_agent_ids.append(AgentID.parse(part))

                debug(
                    f"Parsed meeting targeting: meeting={parsed_meeting_id}, targets={target_agent_ids}"
                )
            elif not parsed_meeting_id:
                # No targeting, just extract meeting ID
                parsed_meeting_id = MeetingID.parse(
                    meeting_spec if "meeting_spec" in locals() else receiver_spec
                )

        # Get sender agent
        sender_agent = self.agents_by_id.get(sender_agent_id.id)
        if not sender_agent:
            raise ValueError(f"Sender agent {sender_agent_id.id} not found")

        # Get or create channel for this communication
        try:
            channel = await self.get_or_create_channel(sender_agent, receiver_spec)
        except ValueError as e:
            debug(f"Error getting channel: {e}")
            return

        # Determine recipient info for the message
        recipient_agent_id = None
        recipient_klass = None

        if receiver_spec.startswith("meeting "):
            # Meeting message - no specific recipient
            if not parsed_meeting_id:
                parsed_meeting_id = MeetingID.parse(receiver_spec)
        else:
            # Direct message - parse recipient
            recipient_agent_id = AgentID.parse(receiver_spec)
            recipient = self.agents_by_id.get(recipient_agent_id.id)
            recipient_klass = recipient.klass if recipient else None

        # Create message with structured IDs
        msg = Message(
            sender_id=sender_agent_id,
            sender_klass=sender_klass,
            content=message_str,
            recipient_klass=recipient_klass,
            recipient_id=recipient_agent_id,
            message_type=message_type,
            meeting_id=parsed_meeting_id,
            target_agent_ids=target_agent_ids,
            stream_id=stream_id,
        )

        # Publish routed-message event for observers (web/cli should subscribe instead of monkey-patching)
        self.event_bus.publish(
            MessageRoutedEvent(
                session_id=self.event_bus.session_id,
                agent_id=sender_agent_id.id,
                channel_id=channel.channel_id,
                message=msg,
            )
        )

        # Publish message sent event for telemetry
        self.event_bus.publish(
            MessageSentEvent(
                session_id=self.event_bus.session_id,
                agent_id=sender_agent_id.id,
                message_id=msg.id,
                sender_id=sender_agent_id.id,
                sender_klass=sender_klass,
                recipients=receiver_spec,
                content_preview=message_str[:100] if message_str else "",
                channel_id=channel.channel_id,
            )
        )

        # Send via channel (channel handles delivery to all participants)
        await channel.send(msg, sender_agent_id.id)

    async def start_stream(
        self: "Program",
        sender_id: str,
        sender_klass: str,
        receiver_spec: str,
        stream_id: str,
        message_type: MessageType = MessageType.DIRECT,
        meeting_id: Optional[str] = None,
    ) -> StreamResult:
        """Start a streaming message via channel.

        Streaming is only used when the recipient is human. For agent-to-agent
        messages, returns a result indicating streaming should be skipped.

        Returns:
            StreamResult indicating whether streaming was started and providing stream_id
        """
        sender_agent = self.agents_by_id.get(AgentID.parse(sender_id).id)
        if not sender_agent:
            return StreamResult.start(stream_id)

        try:
            channel = await self.get_or_create_channel(sender_agent, receiver_spec)

            # Check if any participant is human (streaming is human-only by default)
            has_human = any(
                isinstance(p, HumanParticipant) for p in channel.participants
            )

            if not has_human and not self.enable_agent_streaming:
                # Agent-to-agent communication: skip streaming unless snoop mode is enabled
                return StreamResult.skip()

            # Resolve recipient info for stream events
            recipient_id = None
            recipient_klass = None

            if receiver_spec in ["human", "user"]:
                recipient_id = "human"
                recipient_agent = self.agents_by_id.get("human")
                recipient_klass = recipient_agent.klass if recipient_agent else "User"
            elif not receiver_spec.startswith("meeting "):
                # Direct agent communication - parse to structured ID
                recipient_agent_id = AgentID.parse(receiver_spec)
                recipient_id = recipient_agent_id.id
                recipient_agent = self.agents_by_id.get(recipient_id)
                if recipient_agent:
                    recipient_klass = recipient_agent.klass

            await channel.start_stream(
                stream_id,
                sender_id,
                sender_klass,
                receiver_spec,
                recipient_id,
                recipient_klass,
            )
            return StreamResult.start(stream_id)
        except ValueError:
            return StreamResult.skip()

    async def stream_chunk(
        self: "Program",
        stream_id: str,
        sender_id: str,
        receiver_spec: str,
        content: str,
    ) -> None:
        """Send a chunk of streaming content via channel."""
        sender_agent = self.agents_by_id.get(AgentID.parse(sender_id).id)
        if not sender_agent:
            return

        try:
            channel = await self.get_or_create_channel(sender_agent, receiver_spec)
            await channel.stream_chunk(stream_id, content)
        except ValueError:
            pass

    async def complete_stream(
        self: "Program",
        stream_id: str,
        sender_id: str,
        receiver_spec: str,
        final_content: Optional[str] = None,
    ) -> None:
        """Complete a streaming message via channel."""
        sender_agent = self.agents_by_id.get(AgentID.parse(sender_id).id)
        if not sender_agent:
            return

        try:
            channel = await self.get_or_create_channel(sender_agent, receiver_spec)

            # Determine recipient info for the message
            if receiver_spec.startswith("meeting "):
                # Meeting message - parse to structured ID
                meeting_id_obj = MeetingID.parse(receiver_spec)
                meeting_id = meeting_id_obj.id
                recipient_id = None
                recipient_klass = None
                message_type = MessageType.MEETING_BROADCAST
            else:
                # Direct message - parse to structured ID
                recipient_agent_id = AgentID.parse(receiver_spec)
                recipient_id = recipient_agent_id.id
                recipient = self.agents_by_id.get(recipient_id)
                recipient_klass = recipient.klass if recipient else None
                meeting_id = None
                message_type = MessageType.DIRECT

            # Create the final message with structured IDs
            final_message = Message(
                sender_id=AgentID.parse(sender_id),
                sender_klass=sender_agent.klass,
                content=final_content or "",
                recipient_klass=recipient_klass,
                recipient_id=AgentID.parse(recipient_id) if recipient_id else None,
                message_type=message_type,
                meeting_id=MeetingID.parse(meeting_id) if meeting_id else None,
                stream_id=stream_id,
            )

            # Complete the stream (this will send the message via channel)
            await channel.complete_stream(stream_id, final_message)
        except ValueError:
            pass


class AgentIdRegistry:
    """Manages sequential agent ID generation.

    Provides unique sequential IDs starting from 1000 for agent instances.
    """

    def __init__(self) -> None:
        """Initialize the registry with starting ID 1000."""
        self._next_id = 1000

    def get_next_id(self) -> str:
        """Get the next sequential agent ID.

        Returns:
            String representation of the next available agent ID
        """
        current_id = self._next_id
        self._next_id += 1
        return str(current_id)


class Program(ProgramAgentsCommunicationMixin):
    def __init__(
        self,
        event_bus: EventBus,
        program_paths: List[str] = None,
        compiled_program_paths: List[str] = None,
        program_content: str = None,
        metadata: dict = {},
        cli_args: Optional[Dict[str, Any]] = None,
        initial_state: Optional[Dict[str, Any]] = None,
        source_file_paths: List[str] = None,
    ):
        self.metadata = metadata
        self.event_bus = event_bus
        self.cli_args = cli_args or {}
        self.initial_state = initial_state or {}

        self.program_paths = program_paths or []
        self.compiled_program_paths = compiled_program_paths or []
        self.source_file_paths = (
            source_file_paths or []
        )  # Original source paths for each compiled file
        self.program_content = program_content
        if self.compiled_program_paths and self.program_content:
            raise ValueError(
                "Both compiled_program_paths and program_content cannot be provided."
            )
        if not self.compiled_program_paths and not self.program_content:
            raise ValueError(
                "Either compiled_program_paths or program_content must be provided."
            )

        self._debug_server = None
        self.agent_id_registry = AgentIdRegistry()
        self.meeting_id_registry = MeetingRegistry()

        # Channel registry for unified communication
        self.channels: Dict[str, Channel] = {}

        # Agent runtime manages execution with asyncio
        self.runtime = AsyncAgentRuntime(program=self)

        # Lock for agent creation to prevent race conditions
        self._agent_creation_lock = asyncio.Lock()

        self.extract_public_json()
        self.parse_metadata()

        self.agent_klasses = {}
        # Note: agent_klasses will be populated in async initialize() method

        self.agents = []
        self.agents_by_klass = {}
        self.agents_by_id = {}

        self.execution_finished = False
        self.initialized = False
        self._has_agent_errors = (
            False  # Track if any agents have had errors for test visibility
        )
        self.enable_agent_streaming = (
            False  # Enable streaming for agent-to-agent messages (for snoop mode)
        )

        # Initialize telemetry handler if enabled
        self._langfuse_handler = None
        if config.langfuse.enabled:
            self._langfuse_handler = LangfuseEventHandler(self.event_bus)

    async def initialize(self) -> None:
        # Create agent classes from AST (requires async for LLM compilation)
        if self.program_content:
            # Using program content directly (no cache file)
            ast = markdown_to_ast(self.program_content)
            self.agent_klasses.update(
                await AgentBuilder.create_agent_classes_from_ast(ast)
            )
        else:
            # Using compiled program paths (cache files)
            for i, markdown_content in enumerate(self.markdown_contents):
                # Use original source file path for relative path resolution
                # (e.g., for memory:// MCP server paths)
                # source_file_paths has one entry per compiled file and points to the original .pb source
                if self.source_file_paths and i < len(self.source_file_paths):
                    source_path = str(Path(self.source_file_paths[i]).resolve())
                elif self.program_paths and i < len(self.program_paths):
                    source_path = str(Path(self.program_paths[i]).resolve())
                else:
                    source_path = None

                ast = markdown_to_ast(markdown_content, source_file_path=source_path)
                self.agent_klasses.update(
                    await AgentBuilder.create_agent_classes_from_ast(ast)
                )

        self.agents = [
            await self.create_agent(klass)
            for klass in self.agent_klasses.values()
            if klass.should_create_instance_at_start()
        ]

        # Set initial state variables on all agents
        if self.initial_state:
            for agent in self.agents:
                if hasattr(agent, "state"):
                    for var_name, var_value in self.initial_state.items():
                        # Check if should be promoted to Artifact based on threshold
                        if len(str(var_value)) > config.artifact_result_threshold:
                            artifact = Artifact(
                                name=var_name,
                                summary=f"Initial state variable: {var_name}",
                                value=var_value,
                            )
                            # Store directly on state using dictionary-style access
                            agent.state[var_name] = artifact

                            # Store artifact for pre-loading into first call stack frame
                            if not hasattr(agent, "_initial_artifacts_to_load"):
                                agent._initial_artifacts_to_load = []
                            agent._initial_artifacts_to_load.append(var_name)
                        else:
                            # Store directly on state using dictionary-style access
                            agent.state[var_name] = var_value
        # Validate public.json count (only for local AI agents, not remote/MCP agents)
        # Remote agents (MCPAgent, RemoteAIAgent) don't have playbooks in the current playbook
        # Allow empty or missing public.json for testing scenarios
        # Get non-empty public json lists
        non_empty_public_jsons = [pj for pj in self.public_jsons if pj]

        # Count only local AI agents that actually have playbooks (non-meeting-only agents)
        # Note: All agents in agent_klasses have playbooks defined in the playbook file
        # Meeting-only agents are those with only meeting playbooks
        ai_agent_count = sum(
            1
            for klass in self.agent_klasses.values()
            if not issubclass(klass, HumanAgent)
            and not issubclass(klass, RemoteAIAgent)  # Exclude remote agents
        )

        # Count agents that have non-meeting playbooks (i.e., have public.json)
        agents_with_public_json = len([pj for pj in self.public_jsons if pj])

        # Only validate if there are explicitly defined public.jsons in the playbook
        # If there are non-empty public jsons, they should match the agents that have them
        # But allow agents without public.json (e.g., meeting-only agents)
        if (
            len(non_empty_public_jsons) > 0
            and agents_with_public_json > 0
            and ai_agent_count < agents_with_public_json
        ):
            raise ValueError(
                "Number of public json definitions exceeds number of agents. "
                f"Got {ai_agent_count} local AI agents but {agents_with_public_json} have public.json"
            )

        # Assign public.json to local AI agents only (humans and remote agents don't have playbooks)
        ai_agent_klasses = [
            klass
            for klass in self.agent_klasses.values()
            if not issubclass(klass, HumanAgent)
            and not issubclass(klass, RemoteAIAgent)  # Exclude remote agents
        ]
        for i, agent_klass in enumerate(ai_agent_klasses):
            if i < len(non_empty_public_jsons):
                agent_klass.public_json = non_empty_public_jsons[i]
                if agent_klass.public_json:
                    for playbook in agent_klass.playbooks.values():
                        if not playbook.description:
                            playbook_jsons = list(
                                filter(
                                    lambda x: x["name"] == playbook.klass,
                                    agent_klass.public_json,
                                )
                            )
                            if playbook_jsons:
                                playbook.description = playbook_jsons[0].get(
                                    "description", ""
                                )

        # Create default human agent if none declared
        has_human_agents = any(
            issubclass(klass, HumanAgent) for klass in self.agent_klasses.values()
        )

        if not has_human_agents:
            # No human agents declared - create default "User:Human" agent
            self.agents.append(
                HumanAgent(
                    event_bus=self.event_bus,
                    agent_id="human",
                    program=self,
                    klass="User",
                    name="User",
                )
            )

        # Agent registration
        for agent in self.agents:
            if agent.klass not in self.agents_by_klass:
                self.agents_by_klass[agent.klass] = []
            if agent not in self.agents_by_klass[agent.klass]:
                self.agents_by_klass[agent.klass].append(agent)
            self.agents_by_id[agent.id] = agent
            agent.program = self

        self.event_agents_changed()

        # Pass 1: Discover playbooks for all agents in parallel
        # This ensures all agents (especially MCP/Remote agents) have their playbooks
        # populated before any agent initializes its system messages.
        discovery_tasks = []
        for agent in self.agents:
            if isinstance(agent, AIAgent):
                discovery_tasks.append(agent.discover_playbooks())
        if discovery_tasks:
            # Individual agent discovery failures should not crash the entire program initialization.
            # This allows for lazy initialization or manual transport setup in tests.
            await asyncio.gather(*discovery_tasks, return_exceptions=True)

        # Pass 2: Initialize all agents sequentially
        # This builds system messages and handles BGN playbooks
        for agent in self.agents:
            try:
                await agent.initialize()
            except Exception as e:
                logger.warning(
                    f"Failed to initialize agent {agent.klass} ({agent.id}): {e}"
                )

        self.initialized = True

    @property
    def markdown_contents(self) -> List[str]:
        if self.program_content:
            return [self.program_content]
        return [file_utils.read_file(path) for path in self.compiled_program_paths]

    @property
    def name(self) -> str:
        """Get the program name for display and tracing.

        Uses metadata name if available, otherwise derives from first program file.
        Always prefixed with "Playbooks: ".

        Returns:
            Program name with "Playbooks: " prefix
        """
        program_name = self.metadata.get("name")
        if not program_name and self.program_paths:
            # Use the first program file name as the trace name
            program_name = Path(self.program_paths[0]).stem
        if not program_name:
            program_name = "Program"

        return f"Playbooks: {program_name}"

    def event_agents_changed(self) -> None:
        for agent in self.agents:
            if isinstance(agent, AIAgent):
                agent.event_agents_changed()

    async def create_agent(
        self, agent_klass: Union[str, Type[BaseAgent]], **kwargs
    ) -> BaseAgent:
        if isinstance(agent_klass, str):
            klass = self.agent_klasses.get(agent_klass)
            if not klass:
                raise ValueError(f"Agent class {agent_klass} not found")
        else:
            klass = agent_klass

        agent = klass(
            self.event_bus,
            self.agent_id_registry.get_next_id(),
            program=self,
        )
        agent.kwargs = kwargs

        # Agent registration (no locking needed in single-threaded asyncio)
        self.agents.append(agent)
        if agent.klass not in self.agents_by_klass:
            self.agents_by_klass[agent.klass] = []
        if agent not in self.agents_by_klass[agent.klass]:
            self.agents_by_klass[agent.klass].append(agent)
        self.agents_by_id[agent.id] = agent
        agent.program = self

        self.event_agents_changed()
        if self._debug_server:
            await self._debug_server.send_thread_started_event(agent.id)

        # Publish creation event for observers (web/cli apps should subscribe instead of monkey-patching)
        self.event_bus.publish(
            AgentCreatedEvent(
                session_id=self.event_bus.session_id,
                agent_id=agent.id,
                agent_klass=agent.klass,
            )
        )

        return agent

    async def get_or_create_agent(self, agent_klass: str, **create_kwargs) -> BaseAgent:
        """Get an available agent or create a new one.

        Finds idle agents of the requested type using load balancing.
        Creates a new agent if all are busy or none exist.

        Args:
            agent_klass: Agent class name (e.g., "AccountantExpert")
            **create_kwargs: Arguments to pass to create_agent()

        Returns:
            Agent instance (either existing idle one or newly created)

        Raises:
            ValueError: If agent_klass is not found in agent_klasses
            RuntimeError: If agent creation fails after registration
        """
        # Validate that the agent class exists
        if agent_klass not in self.agent_klasses:
            raise ValueError(
                f"Agent class '{agent_klass}' not found. "
                f"Available classes: {list(self.agent_klasses.keys())}"
            )

        # Use lock to prevent race conditions in async context
        async with self._agent_creation_lock:
            # Get all agents of this type
            agents = self.agents_by_klass.get(agent_klass, [])

            # Find idle agents (not busy) with defensive checks
            idle_agents = []
            for agent in agents:
                # Defensive check: ensure agent has state and variables
                if not hasattr(agent, "state"):
                    logger.debug(
                        f"Agent {agent.id if hasattr(agent, 'id') else 'unknown'} "
                        "missing state attribute, skipping in get_or_create_agent"
                    )
                    continue
                # Check if agent is idle (not busy)
                if not is_agent_busy(agent):
                    idle_agents.append(agent)

            # Load balance: randomly select from idle agents
            if idle_agents:
                return random.choice(idle_agents)

            # Create new agent if all busy or none exist
            # Track registration state for rollback on failure
            new_agent = None
            agent_registered = False
            try:
                new_agent = await self.create_agent(agent_klass, **create_kwargs)
                agent_registered = True

                # For AIAgents, ensure discovery and initialization are complete
                # before the background task starts execution
                if isinstance(new_agent, AIAgent):
                    try:
                        await new_agent.discover_playbooks()
                        await new_agent.initialize()
                    except Exception as e:
                        logger.warning(
                            f"Lazy initialization failed for agent {new_agent.klass} ({new_agent.id}): {e}"
                        )

                await self.runtime.start_agent(new_agent)
                return new_agent
            except Exception as e:
                # Rollback: remove agent from registries if it was registered
                if agent_registered and new_agent is not None:
                    self.agents.remove(new_agent)
                    if agent_klass in self.agents_by_klass:
                        if new_agent in self.agents_by_klass[agent_klass]:
                            self.agents_by_klass[agent_klass].remove(new_agent)
                    if new_agent.id in self.agents_by_id:
                        del self.agents_by_id[new_agent.id]
                    self.event_agents_changed()
                raise RuntimeError(
                    f"Failed to create or start agent '{agent_klass}': {e}"
                ) from e

    async def _start_new_agent(self, agent: BaseAgent) -> None:
        """Initialize and start a newly created agent."""
        try:
            # Start agent as asyncio task
            await self.runtime.start_agent(agent)
        except Exception as e:
            # Log error with full stack trace and re-raise to prevent silent failures
            logger.error(
                f"Error initializing new agent {agent.id}: {str(e)}", exc_info=True
            )
            debug("Agent initialization error", agent_id=agent.id, error=str(e))
            # Store the error on the agent for debugging
            agent._initialization_error = e
            # Re-raise to ensure the caller knows about the failure
            raise RuntimeError(
                f"Failed to initialize agent {agent.id}: {str(e)}"
            ) from e

    def _get_compiled_file_name(self) -> str:
        """Generate the compiled file name based on the first original file."""
        return self.compiled_program_paths[0]

    def _emit_compiled_program_event(self) -> None:
        """Emit an event with the compiled program content for debugging."""
        compiled_file_path = self._get_compiled_file_name()
        event = CompiledProgramEvent(
            session_id="program",
            compiled_file_path=compiled_file_path,
            content=file_utils.read_file(compiled_file_path),
            original_file_paths=self.program_paths,
        )
        self.event_bus.publish(event)

    def parse_metadata(self) -> None:
        self.title = self.metadata.get("title", None)
        self.description = self.metadata.get("description", None)

    def extract_public_json(self) -> None:
        # Extract publics.json from full_program
        self.public_jsons = []

        for markdown_content in self.markdown_contents:
            matches = re.findall(
                r"(```public\.json(.*?)```)", markdown_content, re.DOTALL
            )
            if matches:
                for match in matches:
                    public_json = json.loads(match[1])
                    self.public_jsons.append(public_json)
                    markdown_content = markdown_content.replace(match[0], "")

    async def begin(self) -> None:
        """Start all agents asynchronously.

        Starts all agents as concurrent asyncio tasks. Agents run
        independently and don't block each other.
        """
        # Start all agents as asyncio tasks concurrently
        tasks = []
        for agent in self.agents:
            task = await self.runtime.start_agent(agent)
            if task:  # Only append if a task was created
                tasks.append(task)
        # Don't wait for tasks - let them run independently

    async def run_till_exit(self) -> None:
        """Run the program until execution finishes.

        Starts all agents and waits for execution to complete. Handles
        ExecutionFinished exceptions and ensures proper shutdown.

        Raises:
            ValueError: If program is not initialized
            Exception: Re-raises unexpected errors after logging
        """
        if not self.initialized:
            raise ValueError("Program not initialized. Call initialize() first.")
        try:
            # Create the execution completion event before starting agents
            self.execution_finished_event = asyncio.Event()

            # If debugging with stop-on-entry, wait for continue before starting execution
            # if self._debug_server and self._debug_server.stop_on_entry:
            #     # Wait for the continue command from the debug server
            #     # NOTE: wait_for_continue now requires agent_id parameter
            #     await self._debug_server.wait_for_continue(agent_id="default")

            await self.begin()
            # Wait for ExecutionFinished to be raised from any agent thread
            # Agent threads are designed to run indefinitely until this exception
            await self.execution_finished_event.wait()
        except ExecutionFinished:
            await self.set_execution_finished(reason="normal", exit_code=0)
        except Exception as e:
            logger.error(
                f"Unexpected error in run_till_exit: {e}",
                exc_info=True,
                extra={"context": "program_execution", "error_type": type(e).__name__},
            )
            debug(
                "Unexpected run_till_exit error",
                error=str(e),
                error_type=type(e).__name__,
            )
            await self.set_execution_finished(reason="error", exit_code=1)
            raise
        finally:
            await self.shutdown()

    def get_agent_errors(self) -> List[Dict[str, Any]]:
        """Get a list of all agent errors that have occurred.

        Returns:
            List of error dictionaries with agent_id, error, and error_type
        """
        errors = []
        for agent in self.agents:
            if hasattr(agent, "_execution_error"):
                errors.append(
                    {
                        "agent_id": agent.id,
                        "agent_name": str(agent),
                        "error": str(agent._execution_error),
                        "error_type": type(agent._execution_error).__name__,
                        "error_obj": agent._execution_error,
                    }
                )
            if hasattr(agent, "_initialization_error"):
                errors.append(
                    {
                        "agent_id": agent.id,
                        "agent_name": str(agent),
                        "error": str(agent._initialization_error),
                        "error_type": type(agent._initialization_error).__name__,
                        "error_obj": agent._initialization_error,
                    }
                )
        return errors

    def has_agent_errors(self) -> bool:
        """Check if any agents have had errors.

        Returns:
            True if any agent has encountered an execution error, False otherwise
        """
        return self._has_agent_errors or len(self.get_agent_errors()) > 0

    async def set_execution_finished(
        self, reason: str = "normal", exit_code: int = 0
    ) -> None:
        """Signal that program execution has finished.

        Sets the execution_finished flag and notifies waiting coroutines
        via the execution_finished_event.

        Args:
            reason: Reason for finishing (e.g., "normal", "error")
            exit_code: Exit code (0 for success, non-zero for errors)
        """
        self.execution_finished = True

        # Wait for all agents to become idle
        await self.runtime.wait_for_all_agents_idle()

        if hasattr(self, "execution_finished_event"):
            self.execution_finished_event.set()
        if self.event_bus:
            termination_event = ProgramTerminatedEvent(
                session_id="program", reason=reason, exit_code=exit_code
            )
            self.event_bus.publish(termination_event)

    async def end_program(self) -> None:
        """End the program."""
        raise ExecutionFinished(EXECUTION_FINISHED)

    async def shutdown(self) -> None:
        """Shutdown all agents and clean up resources."""
        await self.set_execution_finished(reason="normal", exit_code=0)

        # Stop all agent tasks via runtime
        await self.runtime.stop_all_agents()

        # Shutdown telemetry handler
        if self._langfuse_handler:
            self._langfuse_handler.shutdown()

        # Shutdown debug server if running
        await self.shutdown_debug_server()

    async def start_debug_server(
        self, host: str = "127.0.0.1", port: int = 7529, stop_on_entry: bool = False
    ) -> None:
        """Start debug client to connect to VSCode debug adapter."""
        # debug(
        #     f"Program.start_debug_server() called with host={host}, port={port}, stop_on_entry={stop_on_entry}",
        # )
        if self._debug_server is None:
            # debug("Creating new DebugServer instance...")
            self._debug_server = DebugServer(program=self, host=host, port=port)

            # Set stop-on-entry flag before starting server
            self._debug_server.set_stop_on_entry(stop_on_entry)
            # debug(f"Stop-on-entry flag set to: {stop_on_entry}")

            # debug("Starting debug server...")
            await self._debug_server.start()

            # Create and connect debug handler AFTER the server has started and socket is connected
            from .debug.debug_handler import DebugHandler

            # debug(
            #     f"[DEBUG] Creating debug handler after server start, client_socket exists: {self._debug_server.client_socket is not None}",
            # )
            debug_handler = DebugHandler(self._debug_server)
            self._debug_server.set_debug_handler(debug_handler)
            # debug("Debug handler created and connected to debug server")

            # Store reference to this program in the debug client
            self._debug_server.set_program(self)

            # Register the program's event bus with the debug client
            self._debug_server.register_bus(self.event_bus)

            for agent in self.agents:
                await self._debug_server.send_thread_started_event(agent.id)
        else:
            debug("Debug server already exists, skipping creation")

    async def shutdown_debug_server(self) -> None:
        """Shutdown the debug client if it's running."""
        if self._debug_server:
            try:
                await self._debug_server.shutdown()
            except Exception as e:
                debug("Error shutting down debug server", error=str(e))
            finally:
                self._debug_server = None

    # Meeting Management Methods

    def get_agents_by_specs(self, specs: List[str]) -> List[BaseAgent]:
        """Get agents by specs."""
        try:
            return [self.agents_by_id[AgentID.parse(spec).id] for spec in specs]
        except KeyError:
            pass

        # Try to get agents by name
        agents = []
        for agent in self.agents:
            name = agent.kwargs.get("name")

            if name and name in specs:
                agents.append(agent)

        if agents and len(agents) == len(specs):
            return agents

        raise ValueError(f"Agent not found. Specs: {specs}")

    def get_agent_by_klass(self, klass: str) -> BaseAgent:
        if klass in ["human", "user", "HUMAN", "USER"]:
            klass = HUMAN_AGENT_KLASS
        try:
            return self.agents_by_klass[klass]
        except KeyError as e:
            raise ValueError(f"Agent with klass {e} not found")

    async def get_agents_by_klasses(self, klasses: List[str]) -> List[BaseAgent]:
        """Get agents by klasses.

        If an agent with a given klass does not exist, it will be created.

        Returns:
            List[BaseAgent]: List of agents found or created for each provided klass.

        Raises:
            KlassNotFoundError: If any klass is not a known klass.
            ValueError: If all provided classes are known klasses
        """
        agents = []
        # Check if all klasses are valid
        for klass in klasses:
            if klass not in self.agent_klasses.keys():
                raise KlassNotFoundError(f"Agent klass {klass} not found")

        # Create agents for any klasses that don't exist
        for klass in klasses:
            if (
                klass not in self.agents_by_klass.keys()
                or not self.agents_by_klass[klass]
            ):
                # If at least one agent does not exist for a klass, create an instance
                await self.create_agent(klass)

            agents.append(self.agents_by_klass[klass][0])

        return agents

    async def get_agents_by_klasses_or_specs(
        self, klasses_or_specs: List[str]
    ) -> List[BaseAgent]:
        """Get agents by specs or klasses."""
        try:
            agents = await self.get_agents_by_klasses(klasses_or_specs)
        except KlassNotFoundError:
            # If any klass is not a known klass, try to get agents by specs
            agents = self.get_agents_by_specs(klasses_or_specs)
        return agents

    # Channel Management Methods

    def _to_participant(
        self, entity: Union[BaseAgent, str]
    ) -> Union[AgentParticipant, HumanParticipant]:
        """Convert an agent or identifier to a Participant.

        Args:
            entity: Agent instance or identifier string

        Returns:
            Participant instance (AgentParticipant or HumanParticipant)
        """
        from .agents.human_agent import HumanAgent

        if isinstance(entity, BaseAgent):
            if isinstance(entity, HumanAgent):
                return HumanParticipant(entity.id, entity.klass, agent=entity)
            return AgentParticipant(entity)
        elif entity in ["human", "user"]:
            human_agent = self.agents_by_id.get("human")
            if human_agent:
                return HumanParticipant(
                    human_agent.id, human_agent.klass, agent=human_agent
                )
            return HumanParticipant("human", "human")
        else:
            raise ValueError(f"Cannot convert {entity} to Participant")

    def _make_channel_id(self, sender_id: str, receiver_id: str) -> str:
        """Create a channel ID for two participants.

        Uses alphabetical ordering to ensure the same channel is used
        regardless of who sends first.

        Args:
            sender_id: ID of the sender
            receiver_id: ID of the receiver

        Returns:
            Channel ID string
        """
        ids = sorted([sender_id, receiver_id])
        return f"channel_{ids[0]}_{ids[1]}"

    async def get_or_create_channel(
        self, sender: BaseAgent, receiver_spec: str
    ) -> Channel:
        """Get or create a channel for communication.

        When a new channel is created, a ChannelCreatedEvent is published to the EventBus
        to enable event-driven channel discovery.

        Args:
            sender: The sending agent
            receiver_spec: Receiver specification (agent ID, meeting ID, etc.)

        Returns:
            Channel instance
        """
        # Handle meeting channels
        if receiver_spec.startswith("meeting "):
            meeting_id_obj = MeetingID.parse(receiver_spec)
            channel_id = f"meeting_{meeting_id_obj.id}"

            # Return existing meeting channel if it exists
            if channel_id in self.channels:
                return self.channels[channel_id]

            # Meeting channel should be created by MeetingManager
            # For now, raise an error if trying to access non-existent meeting channel
            raise ValueError(
                f"Meeting channel {channel_id} does not exist. Meetings must create their channels."
            )

        # Handle direct communication (agent-to-agent, agent-to-human)
        if receiver_spec in ["human", "user"]:
            receiver_id = "human"
            receiver = self.agents_by_id.get("human")
        else:
            receiver_agent_id = AgentID.parse(receiver_spec)
            receiver_id = receiver_agent_id.id
            receiver = self.agents_by_id.get(receiver_id)

        if not receiver:
            raise ValueError(f"Receiver {receiver_spec} not found")

        # Create channel ID (consistent ordering)
        channel_id = self._make_channel_id(sender.id, receiver_id)

        # Atomic check-and-set to avoid race conditions
        existing_channel = self.channels.get(channel_id)
        if existing_channel is not None:
            return existing_channel

        # Create new channel
        participants = [
            self._to_participant(sender),
            self._to_participant(receiver),
        ]
        new_channel = Channel(channel_id, participants)

        # Use setdefault for atomic insertion (returns existing if already set)
        channel = self.channels.setdefault(channel_id, new_channel)

        # Publish event if we actually created a new channel
        if channel is new_channel:
            participant_ids = [p.id for p in participants]
            event = ChannelCreatedEvent(
                session_id=self.event_bus.session_id,
                agent_id="",
                channel_id=channel_id,
                is_meeting=False,
                participant_ids=participant_ids,
            )
            self.event_bus.publish(event)

        return channel

    async def create_meeting_channel(
        self, meeting_id: str, participants: List[BaseAgent]
    ) -> Channel:
        """Create a channel for a meeting.

        This is called by MeetingManager when creating a meeting.
        When a new channel is created, a ChannelCreatedEvent is published to the EventBus.

        Args:
            meeting_id: ID of the meeting
            participants: List of participant agents

        Returns:
            Channel instance
        """
        channel_id = f"meeting_{meeting_id}"

        # Atomic check-and-set to avoid race conditions
        existing_channel = self.channels.get(channel_id)
        if existing_channel is not None:
            return existing_channel

        # Convert all participants to Participant instances
        channel_participants = [self._to_participant(p) for p in participants]

        # Create new channel
        new_channel = Channel(channel_id, channel_participants)

        # Use setdefault for atomic insertion
        channel = self.channels.setdefault(channel_id, new_channel)

        # Publish event if we actually created a new channel
        if channel is new_channel:
            participant_ids = [p.id for p in channel_participants]
            event = ChannelCreatedEvent(
                session_id=self.event_bus.session_id,
                agent_id="",
                channel_id=channel_id,
                is_meeting=True,
                participant_ids=participant_ids,
            )
            self.event_bus.publish(event)

        return channel
