"""Python code executor for self-bound agent methods.

This module executes LLM-generated Python code as bound methods on agent
instances, with 'self' naturally referring to the agent.
"""

import ast
import asyncio
import logging
import traceback
import types
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from box import Box

from playbooks.core.constants import EOM
from playbooks.core.identifiers import AgentID, MeetingID
from playbooks.debug.debug_handler import NoOpDebugHandler
from playbooks.execution.call import PlaybookCall
from playbooks.execution.step import PlaybookStep
from playbooks.state.call_stack import InstructionPointer
from playbooks.state.variables import Artifact

if TYPE_CHECKING:
    from playbooks.agents import LocalAIAgent

logger = logging.getLogger(__name__)

# Constants for namespace building
EXCLUDED_NAMESPACE_KEYS = ["agent", "self"]


class ExecutionResult:
    """Result of executing Python code as a bound agent method.

    Captures all directives and state changes from executing LLM-generated
    Python code, including steps, messages, variables, artifacts, and control flow.
    """

    def __init__(self) -> None:
        """Initialize an empty execution result."""
        self.steps: List[InstructionPointer] = []
        self.messages: List[Tuple[str, str]] = []  # List of (recipient, message)
        self.artifacts: Dict[str, Artifact] = {}  # Artifacts captured
        self.triggers: List[str] = []  # Trigger names
        self.playbook_calls: List[PlaybookCall] = []  # Playbook calls
        self.return_value: Optional[Any] = None
        self.wait_for_user_input = False
        self.wait_for_agent_input = False
        self.wait_for_agent_target: Optional[str] = None
        self.playbook_finished = False
        self.exit_program = False
        self.is_thinking = False

        # Error tracking
        self.syntax_error: Optional[SyntaxError] = None
        self.runtime_error: Optional[Exception] = None
        self.error_message: Optional[str] = None
        self.error_traceback: Optional[str] = None


class PythonExecutor:
    """Executes Python code as bound methods on agent instances."""

    def __init__(self, agent: "LocalAIAgent") -> None:
        """Initialize Python executor.

        Args:
            agent: The AI agent executing the code (provides access to state and program)
        """
        self.agent = agent
        self.result = ExecutionResult()
        self.debug_handler = (
            agent.program._debug_server.debug_handler
            if agent.program and agent.program._debug_server
            else NoOpDebugHandler()
        )
        self.current_instruction_pointer: Optional[InstructionPointer] = (
            self.agent.call_stack.peek()
        )

    def _handle_syntax_error(self, e: SyntaxError) -> ExecutionResult:
        """Handle syntax error by populating result.

        Args:
            e: The SyntaxError exception

        Returns:
            ExecutionResult with error details populated
        """
        self.result.syntax_error = e
        self.result.error_message = f"SyntaxError: {e}"
        self.result.error_traceback = traceback.format_exc()
        return self.result

    def build_namespace(self) -> Dict[str, Any]:
        """Build minimal namespace for generated code execution.

        Code executes as if inside an agent instance method, so 'self'
        is bound to the agent. Most functionality accessed via self.

        Returns:
            Dict containing necessary functions and variables
        """
        # Minimal namespace - most things accessed via self
        namespace = {}

        # Add builtins with dangerous ones removed
        import builtins

        blocked_builtins = {
            "eval",
            "exec",
            "compile",
            "__import__",
            "open",
            "input",
            "breakpoint",
            "exit",
            "quit",
            "help",
            "license",
            "copyright",
            "credits",
        }

        for name in dir(builtins):
            if not name.startswith("_") and name not in blocked_builtins:
                namespace[name] = getattr(builtins, name)

        # Add asyncio for await syntax
        namespace["asyncio"] = asyncio

        # Add Box for meeting shared state and general use
        namespace["Box"] = Box

        # Add agent's namespace items (imports, playbook wrappers, etc.)
        if hasattr(self.agent, "namespace_manager") and hasattr(
            self.agent.namespace_manager, "namespace"
        ):
            agent_namespace = self.agent.namespace_manager.namespace
            # Check if namespace is actually iterable (not a Mock)
            if hasattr(agent_namespace, "items") and callable(agent_namespace.items):
                try:
                    # Only add non-conflicting items
                    for key, value in agent_namespace.items():
                        if key not in namespace and key not in EXCLUDED_NAMESPACE_KEYS:
                            namespace[key] = value
                except TypeError:
                    # Skip if namespace is not iterable (e.g., Mock in tests)
                    pass

        # Add meeting object if agent is in a meeting context
        # Use the most proximal meeting (closest to top of call stack)
        meeting = self.agent.get_current_meeting()
        if meeting is not None:
            namespace["meeting"] = meeting

        return namespace

    async def execute(
        self, code: str, playbook_args: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """Execute Python code as if it's a method on the agent instance.

        The code is transformed into an async method and bound to the agent,
        so 'self' naturally refers to the agent instance.

        Args:
            code: Python code to execute
            playbook_args: Optional dict of playbook argument names to values

        Returns:
            ExecutionResult containing captured directives and any errors
        """
        self.result = ExecutionResult()

        if (
            hasattr(self.agent, "program")
            and self.agent.program
            and getattr(self.agent.program, "execution_finished", False)
        ):
            self.result.playbook_finished = True
            self.result.return_value = "Program execution finished"
            return self.result

        # Set executor on current call stack frame for Log* methods
        # This automatically handles nested execution contexts - when the frame
        # is popped, the previous frame's executor becomes current
        current_frame = self.agent.call_stack.peek()
        if current_frame:
            current_frame.executor = self

            # Store playbook arguments in frame locals
            if playbook_args:
                current_frame.locals.update(playbook_args)

        try:
            # Build namespace (without playbook_args)
            namespace = self.build_namespace()

            # Parse and transform code into async method
            try:
                parsed = ast.parse(code)

                # Create method that takes self as parameter
                func_def = ast.AsyncFunctionDef(
                    name="__exec_method__",
                    args=ast.arguments(
                        posonlyargs=[],
                        args=[
                            ast.arg(arg="self", annotation=None)
                        ],  # Add self parameter
                        kwonlyargs=[],
                        kw_defaults=[],
                        defaults=[],
                    ),
                    body=parsed.body,
                    decorator_list=[],
                    returns=None,
                )
                module = ast.Module(body=[func_def], type_ignores=[])
                ast.fix_missing_locations(module)
                code = ast.unparse(module)
            except SyntaxError as e:
                return self._handle_syntax_error(e)

            # Compile and execute
            try:
                compiled_code = compile(code, "<llm>", "exec")
            except SyntaxError as e:
                return self._handle_syntax_error(e)

            # Execute to get the function
            temp_namespace = {}
            exec(compiled_code, temp_namespace)
            method = temp_namespace["__exec_method__"]

            # Merge namespace with frame locals and self/agent reference
            execution_namespace = namespace.copy()
            if current_frame:
                execution_namespace.update(current_frame.locals)
            execution_namespace["self"] = self.agent
            execution_namespace["agent"] = self.agent  # Allow 'agent' as alias

            # Create bound method with merged namespace
            bound_method = types.MethodType(
                types.FunctionType(
                    method.__code__,
                    execution_namespace,
                    method.__name__,
                    method.__defaults__,
                    method.__closure__,
                ),
                self.agent,
            )

            # Execute the bound method (self is automatically the agent, and agent = self)
            await bound_method()

        except SyntaxError as e:
            return self._handle_syntax_error(e)

        except Exception as e:
            self.result.runtime_error = e
            self.result.error_message = f"{type(e).__name__}: {e}"
            self.result.error_traceback = traceback.format_exc()

        # No cleanup needed - executor is tied to call stack frame lifecycle
        # When the frame is popped, the previous frame's executor becomes current
        return self.result

    async def capture_step(self, location: str) -> None:
        """Capture step execution and update call stack.

        Args:
            location: Step location string (e.g., "Welcome:01:QUE")
        """
        instruction_pointer = self.agent.parse_instruction_pointer(location)
        self.result.steps.append(instruction_pointer)
        self.agent.call_stack.advance_instruction_pointer(instruction_pointer)
        self.current_instruction_pointer = instruction_pointer

        # Try to resolve the actual playbook code for this step so we can label spans
        step_code: Optional[str] = None
        step_obj = getattr(instruction_pointer, "step", None)

        if not step_obj:
            playbook = (
                self.agent.playbooks.get(instruction_pointer.playbook)
                if hasattr(self.agent, "playbooks")
                else None
            )
            if playbook and hasattr(playbook, "get_step"):
                step_obj = playbook.get_step(instruction_pointer.line_number)

        step_type: Optional[str] = None

        if isinstance(step_obj, PlaybookStep):
            raw_text = getattr(step_obj, "raw_text", None)
            if raw_text:
                step_code = f"{instruction_pointer.playbook}:{raw_text}"
            step_type = step_obj.step_type
        elif isinstance(step_obj, str):
            step_code = f"{instruction_pointer.playbook}:{step_obj}"
            step_type = step_obj
        elif step_obj is not None:
            raw_text = getattr(step_obj, "raw_text", None)
            if raw_text:
                step_code = f"{instruction_pointer.playbook}:{raw_text}"

        if not step_type:
            # Attempt to derive from the location string (Playbook:Line:TYPE)
            location_parts = location.split(":")
            if len(location_parts) >= 3:
                step_type = location_parts[2]

        if not step_code:
            step_code = location

        # Check if this is a thinking step
        is_thinking = step_type == "TNK"
        if is_thinking:
            self.result.is_thinking = True

        await self.debug_handler.pause_if_needed(
            instruction_pointer=instruction_pointer,
            agent_id=self.agent.id,
        )

    async def capture_artifact(self, name: str, summary: str, content: str) -> None:
        """Capture artifact creation and store in agent state.

        Args:
            name: Artifact name
            summary: Artifact summary
            content: Artifact content
        """
        artifact = Artifact(name=name, summary=summary, value=content)
        self.result.artifacts[name] = artifact
        setattr(self.agent.state, name, artifact)

    async def capture_trigger(self, code: str) -> None:
        """Capture trigger execution.

        Args:
            code: Trigger code/name
        """
        self.result.triggers.append(code)

    async def capture_return(self, value: Any = None) -> None:
        """Capture return value and mark playbook as finished.

        Args:
            value: Return value
        """
        self.result.return_value = value
        self.agent.state._ = value
        self.result.playbook_finished = True

    async def capture_yld(self, target: str = "user") -> Optional[str]:
        """Capture yield point and handle waiting logic.

        Args:
            target: Yield target ("user", "human", agent_id, etc.)
        """
        target_lower = target.lower()
        # Determine the action type
        if target_lower in ["user", "human"]:
            self.result.wait_for_user_input = True
        elif target_lower == "exit":
            self.result.exit_program = True
        elif target_lower == "return":
            self.result.playbook_finished = True
        else:
            # Agent ID or meeting spec
            self.result.wait_for_agent_input = True
            self.result.wait_for_agent_target = target

        # Perform the actual waiting operations
        messages = []
        if target_lower in ["user", "human"]:
            messages = await self.agent.WaitForMessage("human")
        elif target_lower not in ["exit", "return"]:
            # Agent ID or meeting spec
            target_agent_id = self._resolve_yld_target(target)
            if target_agent_id:
                # Check if this is a meeting target
                if target_agent_id.startswith("meeting "):
                    meeting_id_obj = MeetingID.parse(target_agent_id)
                    meeting_id = meeting_id_obj.id
                    if meeting_id == "current":
                        meeting_id = self.agent.call_stack.peek().meeting_id
                    messages = await self.agent.WaitForMessage(
                        f"meeting {meeting_id}", timeout=10.0
                    )
                    # On timeout, return None (do not inject a synthetic message into the meeting).
                else:
                    # Agent-to-agent communication with progressive timeout notifications
                    return await self._wait_for_agent_with_timeout_notifications(
                        target_agent_id
                    )
        if messages:
            return "\n".join(
                [message.content for message in messages if message.content != EOM]
            )
        return None

    def _resolve_yld_target(self, target: str) -> Optional[str]:
        """Resolve a YLD target to an agent ID.

        Args:
            target: The YLD target specification (agent ID, meeting ID, etc.)

        Returns:
            Resolved agent/meeting ID string or None if target couldn't be resolved
        """
        if not target:
            return None

        # Use the unified target resolver with no fallback for YLD
        # (YLD should be explicit about what it's waiting for)
        return self.agent.resolve_target(target, allow_fallback=False)

    async def _wait_for_agent_with_timeout_notifications(
        self, target_agent_id: str
    ) -> Optional[str]:
        """Wait for agent response with progressive timeout notifications.

        This method waits for a response from a specific agent with periodic
        timeout checks. On each timeout, it:
        1. Checks for messages from the target agent
        2. Collects any interrupt messages from other sources (user, other agents)
        3. Returns a combined message with interrupts + system timeout notification

        The LLM can then decide whether to continue waiting (by calling Yld() again)
        or take alternative action. There is no hard maximum wait time - the LLM
        decides when to give up based on task context.

        Args:
            target_agent_id: The resolved agent ID to wait for

        Returns:
            - Response from target agent if received
            - Combined message with interrupts + timeout notification if timeout
            - None if target_agent_id is invalid
        """
        if not target_agent_id:
            return None

        timeout_interval = 5.0  # Check every 5 seconds
        total_waited = 0.0

        while True:  # No max_wait - LLM decides when to give up
            # Wait for target agent with timeout
            messages = await self.agent.WaitForMessage(
                target_agent_id, timeout=timeout_interval
            )

            # Check if we got messages FROM THE TARGET agent
            if messages:
                target_agent_id_parsed = AgentID.parse(target_agent_id)
                target_messages = [
                    m
                    for m in messages
                    if m.sender_id == target_agent_id_parsed and m.content != EOM
                ]
                if target_messages:
                    # SUCCESS - got response from target!
                    # Note: WaitForMessage() already called _process_collected_messages_from_queue()
                    # which added the AgentCommunicationLLMMessage to call stack
                    return "\n".join([m.content for m in target_messages])

            # Timeout - check for interrupt messages from OTHER sources
            total_waited += timeout_interval

            # Quick check for any other messages (user, other agents, meetings)
            # Use a very short timeout to avoid blocking
            try:
                interrupt_messages = await self.agent.WaitForMessage("*", timeout=0.1)
            except asyncio.TimeoutError:
                interrupt_messages = []

            # Filter: exclude target agent and EOM
            target_id = AgentID.parse(target_agent_id)
            interrupts = [
                m
                for m in interrupt_messages
                if m.sender_id != target_id and m.content != EOM
            ]

            # Note: WaitForMessage("*") already processed all messages and added them
            # to call stack via _process_collected_messages_from_queue()
            # We just need to build the response string

            # Build response: interrupts + system timeout message
            response_parts = []

            # Add interrupt messages first (if any)
            for msg in interrupts:
                response_parts.append(
                    f"Received message from {msg.sender_klass}({msg.sender_id.id}): {msg.content}"
                )

            # Add system timeout notification
            response_parts.append(
                f"System: {target_agent_id} hasn't replied in {total_waited:.0f} seconds. "
                f'You may continue waiting by calling await self.Yld("{target_agent_id}") again, '
                f"or proceed with other actions if this seems too long for the expected task."
            )

            # Build combined message
            combined_message = "\n".join(response_parts)

            # Add to call stack as AgentCommunicationLLMMessage so LLM sees it in next context
            from playbooks.llm.messages import AgentCommunicationLLMMessage

            agent_comm_msg = AgentCommunicationLLMMessage(
                combined_message,
                sender_agent="System",
                target_agent=self.agent.klass,
            )
            self.agent.call_stack.add_llm_message(agent_comm_msg)

            # Return combined message - LLM decides what to do
            return combined_message
