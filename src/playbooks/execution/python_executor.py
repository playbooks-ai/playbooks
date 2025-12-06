"""Python code executor with controlled namespace and capture functions.

This module provides execution of LLM-generated Python code with injected
capture functions (Step, Say, Var, etc.) that record directives.
"""

import ast
import asyncio
import logging
import traceback
import types
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from playbooks.agent_proxy import create_agent_proxies, create_playbook_wrapper
from playbooks.core.identifiers import MeetingID
from playbooks.debug.debug_handler import NoOpDebugHandler
from playbooks.execution.call import PlaybookCall
from playbooks.execution.step import PlaybookStep
from playbooks.state.call_stack import InstructionPointer
from playbooks.state.variables import Artifact
from playbooks.utils.langfuse_client import get_client

if TYPE_CHECKING:
    from playbooks.agents import LocalAIAgent

logger = logging.getLogger(__name__)


class ExecutionResult:
    """Result of executing Python code with capture functions.

    Captures all directives and state changes from executing LLM-generated
    Python code, including steps, messages, variables, artifacts, and control flow.
    """

    def __init__(self) -> None:
        """Initialize an empty execution result."""
        self.steps: List[InstructionPointer] = []
        self.messages: List[Tuple[str, str]] = []  # List of (recipient, message)
        self.vars: Dict[str, Any] = {}  # Variables captured by Var()
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
    """Executes Python code with controlled namespace and capture functions."""

    def __init__(self, agent: "LocalAIAgent") -> None:
        """Initialize Python executor.

        Args:
            agent: The AI agent executing the code (provides access to state and program)
        """
        self.agent = agent
        self.result = ExecutionResult()
        self.debug_handler = (
            agent.program._debug_server.debug_handler
            if agent.program._debug_server
            else NoOpDebugHandler()
        )
        self.current_instruction_pointer: Optional[InstructionPointer] = (
            self.agent.state.call_stack.peek()
        )
        self._base_namespace_cache: Optional[Dict[str, Any]] = None

    def _build_base_namespace(self) -> Dict[str, Any]:
        """Build the static/cacheable part of the namespace.

        This includes:
        - Capture functions (Step, Say, Var, etc.)
        - Playbook wrappers
        - Agent proxies
        - Builtins (with dangerous ones blocked)
        - asyncio module

        The result is cached and reused across executions to improve performance.

        Returns:
            Dictionary with static namespace entries (functions, modules, etc.)
        """
        base_namespace = {
            "Step": self._capture_step,
            "Say": self._capture_say,
            "Var": self._capture_var,
            "Artifact": self._capture_artifact,
            "Trigger": self._capture_trigger,
            "Return": self._capture_return,
            "Yld": self._capture_yld,
            "asyncio": asyncio,
        }

        # Add playbook functions from registry
        if hasattr(self.agent, "playbooks"):
            for playbook_name, playbook in self.agent.playbooks.items():
                # Note: Say() wrapper needs namespace, so we'll create it fresh each time
                if playbook_name != "Say":
                    base_namespace[playbook_name] = create_playbook_wrapper(
                        playbook_name=playbook_name,
                        current_agent=self.agent,
                        namespace=None,  # Will be set in build_namespace()
                    )

        # Add agent proxies (these are static per agent)
        agent_proxies = create_agent_proxies(self.agent, None)
        base_namespace.update(agent_proxies)

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
                base_namespace[name] = getattr(builtins, name)

        return base_namespace

    def build_namespace(
        self, playbook_args: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build namespace with injected capture functions.

        Uses caching for static parts (capture functions, playbooks, builtins)
        and adds dynamic parts (state, playbook args) fresh each time.

        Args:
            playbook_args: Optional dict of playbook argument names to values

        Returns:
            Dict containing all necessary functions and variables
        """
        # Build or reuse base namespace cache
        if self._base_namespace_cache is None:
            self._base_namespace_cache = self._build_base_namespace()

        # Shallow copy the base namespace for this execution
        namespace = self._base_namespace_cache.copy()

        # Add Say() wrapper (needs fresh namespace reference)
        if hasattr(self.agent, "playbooks") and "Say" in self.agent.playbooks:
            namespace["Say"] = self._create_say_wrapper()

        # Update playbook wrappers with the namespace reference
        if hasattr(self.agent, "playbooks"):
            for playbook_name in self.agent.playbooks:
                if playbook_name != "Say" and playbook_name in namespace:
                    wrapper = namespace[playbook_name]
                    if hasattr(wrapper, "namespace"):
                        wrapper.namespace = namespace

        # Add state object for direct attribute access (state.x syntax)
        if self.agent.state and hasattr(self.agent.state, "variables"):
            namespace["state"] = self.agent.state.variables

        # Add playbook arguments
        if playbook_args:
            namespace.update(playbook_args)

        return namespace

    async def execute(
        self, code: str, playbook_args: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """Execute Python code and return captured results.

        Builds namespace, compiles, and executes in a controlled environment.
        All directives (Step, Say, Artifact, etc.) are captured via namespace functions.
        Variables are accessed via state.x syntax (TrackedDotMap).

        Args:
            code: Python code to execute (uses state.x syntax for variables)
            playbook_args: Optional dict of playbook argument names to values

        Returns:
            ExecutionResult containing captured directives and any errors
        """
        self.result = ExecutionResult()

        try:
            # Build namespace with capture functions and state
            namespace = self.build_namespace(playbook_args=playbook_args)

            # Wrap code in async function for execution
            try:
                parsed = ast.parse(code)
                func_def = ast.AsyncFunctionDef(
                    name="__async_exec__",
                    args=ast.arguments(
                        posonlyargs=[],
                        args=[],
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
                self.result.syntax_error = e
                self.result.error_message = f"SyntaxError: {e}"
                logger.error(f"Syntax error during parsing: {e}")
                self.result.error_traceback = traceback.format_exc()
                return self.result

            # Compile code
            try:
                compiled_code = compile(code, "<llm>", "exec")
            except SyntaxError as e:
                self.result.syntax_error = e
                self.result.error_message = f"SyntaxError: {e}"
                logger.error(f"Syntax error compiling code: {e}")
                self.result.error_traceback = traceback.format_exc()
                return self.result

            # Execute the compiled code
            temp_namespace = {}
            exec(compiled_code, temp_namespace)
            fn = temp_namespace["__async_exec__"]
            fn_copy = types.FunctionType(
                fn.__code__,
                namespace,
                fn.__name__,
                fn.__defaults__,
                fn.__closure__,
            )

            await fn_copy()

        except SyntaxError as e:
            self.result.syntax_error = e
            self.result.error_message = f"SyntaxError: {e}"
            logger.error(f"Syntax error executing code: {e}")
            self.result.error_traceback = traceback.format_exc()

        except Exception as e:
            self.result.runtime_error = e
            self.result.error_message = f"{type(e).__name__}: {e}"
            logger.error(f"Error executing code: {type(e).__name__}: {e}")
            self.result.error_traceback = traceback.format_exc()

        return self.result

    async def _capture_step(self, location: str) -> None:
        """Capture Step() call.

        Args:
            location: Step location string (e.g., "Welcome:01:QUE")
        """
        instruction_pointer = self.agent.parse_instruction_pointer(location)
        self.result.steps.append(instruction_pointer)
        self.agent.state.call_stack.advance_instruction_pointer(instruction_pointer)
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

        try:
            langfuse = get_client()
            if langfuse and hasattr(langfuse, "update_current_span"):
                langfuse.update_current_span(name=step_code)
        except Exception as exc:
            logger.debug("Failed to update Langfuse span with step code: %s", exc)

        # Check if this is a thinking step
        is_thinking = step_type == "TNK"
        if is_thinking:
            self.result.is_thinking = True

        await self.debug_handler.pause_if_needed(
            instruction_pointer=instruction_pointer,
            agent_id=self.agent.id,
        )

    async def _capture_say(self, target: str, message: str) -> None:
        """Capture Say() call.

        Args:
            target: Message recipient ("user", "human", agent_id, etc.)
            message: Message content
        """
        self.result.messages.append((target, message))

    async def _capture_var(self, name: str, value: Any) -> None:
        """Capture variable and update state.

        Args:
            name: Variable name
            value: Variable value
        """
        from playbooks.config import config

        # Auto-convert large values to artifacts
        if len(str(value)) > config.artifact_result_threshold:
            artifact = Artifact(
                name=name,
                summary=f"Variable: {name}",
                value=str(value),
            )
            self.result.vars[name] = artifact
            if self.agent.state:
                setattr(self.agent.state.variables, name, artifact)
        else:
            self.result.vars[name] = value
            if self.agent.state:
                setattr(self.agent.state.variables, name, value)

    async def _capture_artifact(self, name: str, summary: str, content: str) -> None:
        """Capture Artifact() call.

        Args:
            name: Artifact name
            summary: Artifact summary
            content: Artifact content
        """
        artifact = Artifact(name=name, summary=summary, value=content)
        self.result.artifacts[name] = artifact
        self.result.vars[name] = artifact

        if self.agent.state:
            setattr(self.agent.state.variables, name, artifact)

    async def _capture_trigger(self, code: str) -> None:
        """Capture Trigger() call.

        Args:
            code: Trigger code/name
        """
        self.result.triggers.append(code)

    async def _capture_return(self, value: Any = None) -> None:
        """Capture Return() call.

        Args:
            value: Return value
        """
        self.result.return_value = value
        if self.agent.state:
            self.agent.state.variables._ = value
        self.result.playbook_finished = True

    async def _capture_yld(self, target: str = "user") -> None:
        """Capture Yld() call.

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
        if target_lower in ["user", "human"]:
            await self.agent.WaitForMessage("human")
        elif target_lower not in ["exit", "return"]:
            # Agent ID or meeting spec
            target_agent_id = self._resolve_yld_target(target)
            if target_agent_id:
                # Check if this is a meeting target
                if target_agent_id.startswith("meeting "):
                    meeting_id_obj = MeetingID.parse(target_agent_id)
                    meeting_id = meeting_id_obj.id
                    if meeting_id == "current":
                        meeting_id = self.agent.state.call_stack.peek().meeting_id
                    await self.agent.WaitForMessage(f"meeting {meeting_id}")
                else:
                    await self.agent.WaitForMessage(target_agent_id)

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

    def _create_say_wrapper(self) -> Callable[[str, str], Any]:
        """Create a wrapper for Say() that ensures proper pre/post processing.

        The wrapper calls execute_playbook to ensure proper logging, langfuse tracking,
        and other pre/post processing. The _currently_streaming flag is checked
        internally by agent.Say() to prevent duplicate output.

        _currently_streaming flag interaction:
        - During LLM streaming, Say("human", "...") calls are pattern-detected and
          displayed in real-time to the user (see execution/playbook.py)
        - The flag is set to True to mark that the message was already streamed
        - When this Python code executes later, Say() checks the flag
        - If True, it skips the streaming path and just delivers the message
        - This prevents showing the same message twice (once streamed, once executed)
        - For agent-to-agent messages, streaming is skipped entirely (human-only)

        Returns:
            Async function that wraps Say() playbook execution
        """

        async def say_wrapper(target: str, message: str) -> Any:
            # Execute the Say() playbook (which will internally check _currently_streaming)
            success, result = await self.agent.execute_playbook(
                "Say", [target, message], {}
            )
            if not success:
                return "ERROR: " + result
            return result

        return say_wrapper
