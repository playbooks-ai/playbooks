"""Langfuse event handler for telemetry.

This module provides an event-driven interface to Langfuse telemetry,
decoupling core business logic from telemetry implementation.
"""

import logging
import time
import uuid
from typing import Any, Dict, Optional

from playbooks.core.events import (
    AgentCreatedEvent,
    AgentTerminatedEvent,
    CompilationEndedEvent,
    CompilationStartedEvent,
    LLMCallEndedEvent,
    LLMCallStartedEvent,
    MessageReceivedEvent,
    MessageSentEvent,
    MethodCallEndedEvent,
    MethodCallStartedEvent,
    PlaybookEndEvent,
    PlaybookStartEvent,
)
from playbooks.infrastructure.event_bus import EventBus
from playbooks.infrastructure.logging.debug_logger import debug
from playbooks.utils.langfuse_helper import LangfuseHelper

logger = logging.getLogger(__name__)


class LangfuseEventHandler:
    """Event handler that translates business events to Langfuse telemetry.

    This handler subscribes to semantic business events and converts them to
    appropriate Langfuse observations, spans, and traces. It maintains internal
    state for span hierarchy and provides no-op behavior when telemetry is disabled.
    """

    def __init__(self, event_bus: EventBus):
        """Initialize the Langfuse event handler.

        Args:
            event_bus: The event bus to subscribe to business events
        """
        self.event_bus = event_bus
        self._active_spans: Dict[str, Any] = {}  # span_key -> langfuse span object
        self._agent_traces: Dict[str, str] = {}  # agent_id -> trace_id
        self._agent_names: Dict[str, str] = {}  # agent_id -> agent_class_name
        self._llm_call_counters: Dict[str, int] = {}  # agent_id -> llm call count
        self._current_llm_generation: Dict[str, Any] = (
            {}
        )  # agent_id -> current active LLM generation
        self._playbook_stack: Dict[str, list] = (
            {}
        )  # agent_id -> stack of active playbook spans
        self._method_call_stack: Dict[str, list] = (
            {}
        )  # agent_id -> stack of active method call spans
        self._session_id: Optional[str] = None

        # Subscribe to semantic business events
        event_bus.subscribe(AgentCreatedEvent, self._handle_agent_created)
        event_bus.subscribe(AgentTerminatedEvent, self._handle_agent_terminated)
        event_bus.subscribe(PlaybookStartEvent, self._handle_playbook_start)
        event_bus.subscribe(PlaybookEndEvent, self._handle_playbook_end)
        event_bus.subscribe(LLMCallStartedEvent, self._handle_llm_call_started)
        event_bus.subscribe(LLMCallEndedEvent, self._handle_llm_call_ended)
        event_bus.subscribe(MethodCallStartedEvent, self._handle_method_call_started)
        event_bus.subscribe(MethodCallEndedEvent, self._handle_method_call_ended)
        event_bus.subscribe(MessageSentEvent, self._handle_message_sent)
        event_bus.subscribe(MessageReceivedEvent, self._handle_message_received)
        event_bus.subscribe(CompilationStartedEvent, self._handle_compilation_started)
        event_bus.subscribe(CompilationEndedEvent, self._handle_compilation_ended)

    def _handle_agent_created(self, event: AgentCreatedEvent) -> None:
        """Handle agent creation by creating a trace."""
        try:
            langfuse = LangfuseHelper.instance()

            # Generate a unique trace ID for this agent
            trace_id = uuid.uuid4().hex
            trace_name = f"{event.agent_klass} (agent {event.agent_id})"

            # Create the single agent root observation that serves as the trace container
            root_observation = langfuse.start_observation(
                name=trace_name,
                as_type="span",
                trace_context={"trace_id": trace_id, "session_id": event.session_id},
                metadata={
                    "agent_klass": event.agent_klass,
                    "is_root": True,
                    "agent_id": event.agent_id,
                },
            )

            # Store trace ID and agent name for hierarchy and trace naming
            self._agent_traces[event.agent_id] = trace_id
            self._agent_names[event.agent_id] = event.agent_klass
            if hasattr(root_observation, "id") and root_observation.id:
                self._active_spans[f"agent_{event.agent_id}_root"] = root_observation
                # Keep root observation active for proper nesting of child observations
                # It will be ended during shutdown

                # Debug output for trace ID
                debug(
                    f"Created ROOT observation 'Agent {event.agent_klass} ({event.agent_id})' at {time.time()}",
                    trace_id=trace_id,
                    root_observation_id=getattr(root_observation, "id", None),
                )

                # Flush to ensure everything is registered
                LangfuseHelper.flush()

        except Exception as e:
            logger.warning(f"Failed to handle agent created event: {e}")

    def _handle_agent_terminated(self, event: AgentTerminatedEvent) -> None:
        """Handle agent termination by updating trace name and ending agent root span."""
        try:
            langfuse = LangfuseHelper.instance()
            if not langfuse.auth_check():
                return

            trace_id = self._agent_traces.get(event.agent_id)
            if not trace_id:
                return

            # End the agent root observation
            agent_root_key = f"agent_{event.agent_id}_root"
            agent_root = self._active_spans.get(agent_root_key)
            if agent_root:
                try:
                    # Update the agent root name before ending it
                    agent_root.update(
                        name=f"{event.agent_klass} (agent {event.agent_id})"
                    )
                    agent_root.end()
                    self._active_spans.pop(agent_root_key, None)

                    debug(
                        f"Ended agent root observation for {event.agent_klass} (agent {event.agent_id})"
                    )
                except Exception as e:
                    logger.warning(f"Failed to end agent root: {e}")

            # Flush to ensure all events are sent BEFORE updating the trace
            LangfuseHelper.flush()

            # Now update the trace name explicitly by creating and immediately ending a final observation
            # Langfuse uses the last observation to update as the trace name
            try:
                # Create a final "trace namer" observation that ends immediately
                trace_namer = langfuse.start_observation(
                    name=f"{event.agent_klass} (agent {event.agent_id})",
                    as_type="event",  # Use event type for instantaneous observations
                    trace_context={
                        "trace_id": trace_id,
                        "session_id": event.session_id,
                    },
                    metadata={"is_trace_namer": True},
                )
                # End it immediately
                if trace_namer:
                    trace_namer.end()

                LangfuseHelper.flush()
                debug(
                    f"Updated trace name to: {event.agent_klass} (agent {event.agent_id})"
                )
            except Exception as e:
                logger.warning(f"Failed to update trace name at termination: {e}")

            # Clean up agent-specific data
            self._agent_traces.pop(event.agent_id, None)
            self._agent_names.pop(event.agent_id, None)
            self._llm_call_counters.pop(event.agent_id, None)
            self._current_llm_generation.pop(event.agent_id, None)
            self._playbook_stack.pop(event.agent_id, None)
            self._method_call_stack.pop(event.agent_id, None)

        except Exception as e:
            logger.warning(f"Failed to handle agent terminated event: {e}")

    def _handle_playbook_start(self, event: PlaybookStartEvent) -> None:
        """Handle playbook start by creating a span."""
        try:
            langfuse = LangfuseHelper.instance()

            # Get trace context from agent
            trace_id = self._agent_traces.get(event.agent_id)
            trace_context = {"session_id": event.session_id}
            if trace_id:
                trace_context["trace_id"] = trace_id

            # Determine parent: current LLM generation > parent playbook > agent root
            # Priority 1: Nest under current LLM generation (the LLM call that invoked this playbook)
            current_llm = self._current_llm_generation.get(event.agent_id)
            if current_llm and hasattr(current_llm, "id") and current_llm.id:
                trace_context["parent_span_id"] = current_llm.id
            else:
                # Priority 2: Nest under parent playbook (if in a playbook call chain)
                if (
                    event.agent_id in self._playbook_stack
                    and self._playbook_stack[event.agent_id]
                ):
                    parent_playbook = self._playbook_stack[event.agent_id][-1]
                    if hasattr(parent_playbook, "id") and parent_playbook.id:
                        trace_context["parent_span_id"] = parent_playbook.id
                else:
                    # Priority 3: Nest under agent root
                    agent_root_key = f"agent_{event.agent_id}_root"
                    agent_root = self._active_spans.get(agent_root_key)
                    if agent_root and hasattr(agent_root, "id") and agent_root.id:
                        trace_context["parent_span_id"] = agent_root.id

            # Create playbook span with proper naming
            agent_class = self._agent_names.get(
                event.agent_id, f"Agent{event.agent_id}"
            )
            playbook_span = langfuse.start_observation(
                name=f"Markdown: {agent_class}.{event.playbook}()",
                as_type="span",
                trace_context=trace_context,
                metadata={"playbook": event.playbook, "agent_class": agent_class},
            )

            # Store span for later reference
            span_key = f"playbook_{event.agent_id}_{event.playbook}_{id(playbook_span)}"
            if hasattr(playbook_span, "id") and playbook_span.id:
                self._active_spans[span_key] = playbook_span

                # Push onto playbook stack
                if event.agent_id not in self._playbook_stack:
                    self._playbook_stack[event.agent_id] = []
                self._playbook_stack[event.agent_id].append(playbook_span)

        except Exception as e:
            logger.warning(f"Failed to handle playbook start event: {e}")

    def _handle_playbook_end(self, event: PlaybookEndEvent) -> None:
        """Handle playbook end by updating and ending the span."""
        try:
            # Pop from playbook stack
            if (
                event.agent_id in self._playbook_stack
                and self._playbook_stack[event.agent_id]
            ):
                ended_span = self._playbook_stack[event.agent_id].pop()

                # Find and remove from active spans
                span_key_to_remove = None
                for key, span in self._active_spans.items():
                    if span is ended_span:
                        span_key_to_remove = key
                        break

                if span_key_to_remove and ended_span:
                    # Update with return value if any
                    if event.return_value is not None:
                        ended_span.update(output=str(event.return_value))

                    ended_span.end()
                    self._active_spans.pop(span_key_to_remove, None)

        except Exception as e:
            logger.warning(f"Failed to handle playbook end event: {e}")

    def _handle_llm_call_started(self, event: LLMCallStartedEvent) -> None:
        """Handle LLM call start by creating a generation observation."""
        try:
            langfuse = LangfuseHelper.instance()

            # Get trace context from agent
            trace_id = self._agent_traces.get(event.agent_id)
            trace_context = {"session_id": event.session_id}
            if trace_id:
                trace_context["trace_id"] = trace_id

            # Nest under the current active playbook (top of stack)
            if (
                event.agent_id in self._playbook_stack
                and self._playbook_stack[event.agent_id]
            ):
                current_playbook = self._playbook_stack[event.agent_id][-1]
                if hasattr(current_playbook, "id") and current_playbook.id:
                    trace_context["parent_span_id"] = current_playbook.id

            # Increment LLM call counter for this agent
            call_number = self._llm_call_counters.get(event.agent_id, 0) + 1
            self._llm_call_counters[event.agent_id] = call_number

            # Create LLM call observation as a generation with proper LLM metadata
            generation = langfuse.start_observation(
                name=f"LLM Call {call_number}",
                as_type="generation",
                trace_context=trace_context,
                model=event.model,
                input=event.input,
                metadata={
                    **event.metadata,
                    "input_tokens": event.input_tokens,
                    "output_tokens": 0,  # Will be updated on end
                    "stream": event.stream,
                    "call_number": call_number,
                },
            )

            # Debug output
            debug(
                f"Created LLM generation observation at {time.time()}",
                trace_id=trace_id,
                generation_id=getattr(generation, "id", None),
            )

            # Store generation for completion
            call_key = f"llm_{event.agent_id}_{event.model}_{id(event)}"
            if hasattr(generation, "id") and generation.id:
                self._active_spans[call_key] = generation
                # Track as the current active LLM generation for this agent
                self._current_llm_generation[event.agent_id] = generation

        except Exception as e:
            logger.warning(f"Failed to handle LLM call started event: {e}")

    def _handle_llm_call_ended(self, event: LLMCallEndedEvent) -> None:
        """Handle LLM call end by updating and ending the generation."""
        try:
            # Find the generation span (this is a bit hacky since we used id(event))
            # In practice, we'd need a better way to correlate start/end events
            # For now, we'll update all active LLM spans for this agent/model
            langfuse_spans = [
                (key, span)
                for key, span in self._active_spans.items()
                if key.startswith(f"llm_{event.agent_id}_{event.model}_")
            ]

            for span_key, span in langfuse_spans:
                # Build update kwargs - output must be passed to update(), not end()
                update_kwargs = {
                    "metadata": {
                        "output_tokens": event.output_tokens,
                        "cache_hit": event.cache_hit,
                    }
                }

                if event.output is not None:
                    update_kwargs["output"] = event.output
                if event.error:
                    update_kwargs["status_message"] = event.error

                span.update(**update_kwargs)
                span.end()
                self._active_spans.pop(span_key, None)

                # Clear current LLM generation if this is the active one
                if self._current_llm_generation.get(event.agent_id) is span:
                    self._current_llm_generation.pop(event.agent_id, None)

            # Flush to ensure updates are sent to Langfuse
            if langfuse_spans:
                LangfuseHelper.flush()

        except Exception as e:
            logger.warning(f"Failed to handle LLM call ended event: {e}")

    def _handle_method_call_started(self, event: MethodCallStartedEvent) -> None:
        """Handle method call start by creating a span."""
        try:
            langfuse = LangfuseHelper.instance()

            # Get trace context from agent
            trace_id = self._agent_traces.get(event.agent_id)
            trace_context = {"session_id": event.session_id}
            if trace_id:
                trace_context["trace_id"] = trace_id

            # Nest under the current active LLM generation for this agent
            current_llm = self._current_llm_generation.get(event.agent_id)
            if current_llm and hasattr(current_llm, "id") and current_llm.id:
                trace_context["parent_span_id"] = current_llm.id

            # Create method call span (use span type to avoid trace naming conflicts)
            method_span = langfuse.start_observation(
                name=f"{event.method_name}({', '.join(str(arg) for arg in (event.args or []))})",
                as_type="span",
                trace_context=trace_context,
                input=f"args={event.args}, kwargs={event.kwargs}",
                metadata={"method_name": event.method_name},
            )

            # Store span for completion - use stack for proper correlation
            if hasattr(method_span, "id") and method_span.id:
                # Push onto method call stack
                if event.agent_id not in self._method_call_stack:
                    self._method_call_stack[event.agent_id] = []
                self._method_call_stack[event.agent_id].append(method_span)

        except Exception as e:
            logger.warning(f"Failed to handle method call started event: {e}")

    def _handle_method_call_ended(self, event: MethodCallEndedEvent) -> None:
        """Handle method call end by updating and ending the span."""
        try:
            # Pop from method call stack
            if (
                event.agent_id in self._method_call_stack
                and self._method_call_stack[event.agent_id]
            ):
                method_span = self._method_call_stack[event.agent_id].pop()

                if method_span:
                    update_kwargs = {}

                    if event.result is not None:
                        update_kwargs["output"] = str(event.result)
                    if event.error:
                        update_kwargs["status_message"] = event.error

                    if update_kwargs:
                        method_span.update(**update_kwargs)
                    method_span.end()

        except Exception as e:
            logger.warning(f"Failed to handle method call ended event: {e}")

    def _handle_message_sent(self, event: MessageSentEvent) -> None:
        """Handle message sent by creating an event span."""
        try:
            langfuse = LangfuseHelper.instance()
            if not langfuse.auth_check():
                return

            # Get trace context from sender agent
            trace_id = self._agent_traces.get(event.sender_id)
            if not trace_id:
                return

            trace_context = {"session_id": event.session_id, "trace_id": trace_id}

            # Nest under the current active playbook or method call
            if (
                event.sender_id in self._method_call_stack
                and self._method_call_stack[event.sender_id]
            ):
                parent_span = self._method_call_stack[event.sender_id][-1]
                if hasattr(parent_span, "id") and parent_span.id:
                    trace_context["parent_span_id"] = parent_span.id
            elif (
                event.sender_id in self._playbook_stack
                and self._playbook_stack[event.sender_id]
            ):
                parent_span = self._playbook_stack[event.sender_id][-1]
                if hasattr(parent_span, "id") and parent_span.id:
                    trace_context["parent_span_id"] = parent_span.id

            # Create event span for message sent
            message_span = langfuse.start_observation(
                name=f"📤 Message sent to {event.recipients}",
                as_type="event",
                trace_context=trace_context,
                input=event.content_preview,
                metadata={
                    "message_id": event.message_id,
                    "sender": event.sender_klass,
                    "recipients": event.recipients,
                    "channel_id": event.channel_id,
                },
            )

            # End immediately (events are instantaneous)
            if message_span:
                message_span.end()

        except Exception as e:
            logger.warning(f"Failed to handle message sent event: {e}")

    def _handle_message_received(self, event: MessageReceivedEvent) -> None:
        """Handle message received by creating an event span."""
        try:
            langfuse = LangfuseHelper.instance()
            if not langfuse.auth_check():
                return

            # Get trace context from recipient agent
            trace_id = self._agent_traces.get(event.recipient_id)
            if not trace_id:
                return

            trace_context = {"session_id": event.session_id, "trace_id": trace_id}

            # Nest under the agent root
            agent_root_key = f"agent_{event.recipient_id}_root"
            agent_root = self._active_spans.get(agent_root_key)
            if agent_root and hasattr(agent_root, "id") and agent_root.id:
                trace_context["parent_span_id"] = agent_root.id

            # Create event span for message received
            message_span = langfuse.start_observation(
                name=f"📥 {event.sender_klass} -> {event.recipient_klass}",
                as_type="event",
                trace_context=trace_context,
                metadata={
                    "message_id": event.message_id,
                    "sender": event.sender_klass,
                    "recipient": event.recipient_klass,
                },
            )

            # End immediately (events are instantaneous)
            if message_span:
                message_span.end()

        except Exception as e:
            logger.warning(f"Failed to handle message received event: {e}")

    def _handle_compilation_started(self, event: CompilationStartedEvent) -> None:
        """Handle compilation start by creating a span."""
        try:
            langfuse = LangfuseHelper.instance()

            # Create compilation span
            compilation_span = langfuse.start_observation(
                name=f"Compile: {event.file_path}",
                as_type="span",
                trace_context={"session_id": event.session_id},
                input=f"Content length: {event.content_length}",
                metadata={"file_path": event.file_path, "operation": "compilation"},
            )

            # Store span
            span_key = f"compile_{event.file_path}_{event.session_id}"
            if hasattr(compilation_span, "id") and compilation_span.id:
                self._active_spans[span_key] = compilation_span

        except Exception as e:
            logger.warning(f"Failed to handle compilation started event: {e}")

    def _handle_compilation_ended(self, event: CompilationEndedEvent) -> None:
        """Handle compilation end by updating and ending the span."""
        try:
            span_key = f"compile_{event.file_path}_{event.session_id}"
            span = self._active_spans.get(span_key)

            if span:
                update_kwargs = {
                    "output": f"Compiled content length: {event.compiled_content_length}"
                }

                if event.error:
                    update_kwargs["status_message"] = event.error

                span.update(**update_kwargs)
                span.end()
                self._active_spans.pop(span_key, None)

        except Exception as e:
            logger.warning(f"Failed to handle compilation ended event: {e}")

    def shutdown(self) -> None:
        """Clean up resources and flush any pending telemetry."""
        try:
            # End all spans in stacks
            for agent_id, stack in list(self._playbook_stack.items()):
                for span in stack:
                    try:
                        span.end()
                    except Exception:
                        pass
                self._playbook_stack[agent_id] = []

            for agent_id, stack in list(self._method_call_stack.items()):
                for span in stack:
                    try:
                        span.end()
                    except Exception:
                        pass
                self._method_call_stack[agent_id] = []

            # End all active spans (includes agent root, etc.)
            for span_key, span in list(self._active_spans.items()):
                try:
                    span.end()
                except Exception:
                    pass
                self._active_spans.pop(span_key, None)

            # Final flush
            LangfuseHelper.flush()

        except Exception as e:
            logger.warning(f"Error during telemetry handler shutdown: {e}")
