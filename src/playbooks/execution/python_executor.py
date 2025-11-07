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
from playbooks.state.call_stack import InstructionPointer
from playbooks.debug.debug_handler import NoOpDebugHandler
from playbooks.core.identifiers import MeetingID
from playbooks.llm.messages.types import ArtifactLLMMessage
from playbooks.execution.call import PlaybookCall
from playbooks.compilation.inject_setvar import inject_setvar
from playbooks.state.variables import Artifact

if TYPE_CHECKING:
    from playbooks.agents import LocalAIAgent

logger = logging.getLogger(__name__)


class LLMNamespace(dict):
    """Custom namespace that tracks variable assignments.

    This namespace intercepts assignments to capture variables and make them
    available to subsequent code. When a variable is assigned (e.g., x = 10),
    the namespace automatically captures it via the executor's _capture_var method.

    Note: The code is pre-processed before execution (e.g., $x = 10 becomes x = 10)
    by preprocess_program() in expression_engine.py, so this namespace just needs
    to intercept the assignments.
    """

    def __init__(self, executor: "PythonExecutor", *args, **kwargs):
        """Initialize the namespace with reference to executor for callbacks.

        Args:
            executor: The PythonExecutor instance that owns this namespace
        """
        super().__init__(*args, **kwargs)
        self.executor = executor

    def __getitem__(self, key: str) -> Any:
        """Get item from namespace, proxying state variables when needed.

        When a variable is requested, first check the local namespace.
        If not found and it looks like a user variable, try to get it from
        the execution state (with $ prefix).

        Args:
            key: The variable name

        Returns:
            The value from namespace or state

        Raises:
            KeyError: If the variable is not found
        """
        # First try the local namespace
        if not key.endswith("_") and key in self:
            return super().__getitem__(key)

        # If not in namespace and looks like a user variable,
        # try to get it from state with $ prefix
        if self.executor.agent.state and hasattr(
            self.executor.agent.state, "variables"
        ):
            state_key = f"${key}"
            if state_key in self.executor.agent.state.variables:
                var = self.executor.agent.state.variables[state_key]
                # Extract the actual value from Variable objects
                from playbooks.state.variables import Variable

                if isinstance(var, Artifact):
                    # Auto-load artifact if not already loaded in any frame
                    if hasattr(
                        self.executor.agent.state, "call_stack"
                    ) and not self.executor.agent.state.call_stack.is_artifact_loaded(
                        state_key
                    ):

                        artifact_msg = ArtifactLLMMessage(var)
                        self.executor.agent.state.call_stack.add_llm_message(
                            artifact_msg
                        )
                    return var
                elif isinstance(var, Variable):
                    return var.value
                else:
                    raise ValueError(f"Invalid variable object: {var}")

        # Not found anywhere, raise KeyError
        raise KeyError(key)


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
    ) -> LLMNamespace:
        """Build namespace with injected capture functions.

        Uses caching for static parts (capture functions, playbooks, builtins)
        and adds dynamic parts (variables, playbook args) fresh each time.

        Args:
            playbook_args: Optional dict of playbook argument names to values

        Returns:
            LLMNamespace containing all necessary functions and variables
        """
        # Build or reuse base namespace cache
        if self._base_namespace_cache is None:
            self._base_namespace_cache = self._build_base_namespace()

        # Shallow copy the base namespace for this execution
        namespace_dict = self._base_namespace_cache.copy()

        # Create LLMNamespace with the copied base
        namespace = LLMNamespace(self, namespace_dict)

        # Add Say() wrapper (needs fresh namespace reference)
        if hasattr(self.agent, "playbooks") and "Say" in self.agent.playbooks:
            dict.__setitem__(namespace, "Say", self._create_say_wrapper())

        # Update playbook wrappers with the namespace reference
        # (they were created with namespace=None in base cache)
        if hasattr(self.agent, "playbooks"):
            for playbook_name, playbook in self.agent.playbooks.items():
                if playbook_name != "Say" and playbook_name in namespace_dict:
                    wrapper = namespace_dict[playbook_name]
                    if hasattr(wrapper, "namespace"):
                        wrapper.namespace = namespace

        # Add dynamic parts: existing variables from state
        if self.agent.state and hasattr(self.agent.state, "variables"):
            for var_name, var_value in self.agent.state.variables.to_dict().items():
                # Strip $ prefix from variable names for the namespace
                clean_name = var_name[1:] if var_name.startswith("$") else var_name
                dict.__setitem__(namespace, clean_name, var_value)

        # Add dynamic parts: playbook arguments
        if playbook_args:
            for arg_name, arg_value in playbook_args.items():
                dict.__setitem__(namespace, arg_name, arg_value)

        return namespace

    async def execute(
        self, code: str, playbook_args: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """Execute Python code and return captured results.

        Preprocesses code, builds namespace, compiles, and executes in a controlled
        environment. All directives (Step, Say, Var, etc.) are captured via the
        namespace functions.

        Args:
            code: Python code to execute (may contain $var = value syntax)
            playbook_args: Optional dict of playbook argument names to values

        Returns:
            ExecutionResult containing captured directives and any errors

        Raises:
            SyntaxError: If code has syntax errors (also captured in result)
            Exception: If code raises an exception (also captured in result)
        """
        self.result = ExecutionResult()

        try:
            # Pre-process code to handle $variable syntax
            # Convert $variable → variable so the code is valid Python
            from playbooks.compilation.expression_engine import preprocess_program

            code = preprocess_program(code)

            # Build namespace with capture functions
            namespace = self.build_namespace(playbook_args=playbook_args)

            # Wrap in async function, then inject Var() calls
            # These can raise SyntaxError if the code has syntax issues
            try:
                # Wrap code in async function for execution first
                # Use AST to properly indent without mangling string literals
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
                # Fix missing location information for manually created AST nodes
                ast.fix_missing_locations(module)
                code = ast.unparse(module)
                # Now inject SetVar calls (works on function bodies)
                code = inject_setvar(code)
            except SyntaxError as e:
                self.result.syntax_error = e
                self.result.error_message = f"SyntaxError: {e}"
                logger.error(f"Syntax error during preprocessing: {e}")
                backtrace = traceback.format_exc()
                logger.error(f"Backtrace: {backtrace}")
                self.result.error_traceback = backtrace
                return self.result

            # Compile code to check for syntax errors early
            try:
                compiled_code = compile(code, "<llm>", "exec")
            except SyntaxError as e:
                self.result.syntax_error = e
                self.result.error_message = f"SyntaxError: {e}"
                logger.error(f"Syntax error executing code: {e}")
                backtrace = traceback.format_exc()
                logger.error(f"Backtrace: {backtrace}")
                self.result.error_traceback = backtrace
                return self.result

            # Execute the compiled code in the controlled namespace
            # This populates namespace with function definitions and executes statements
            # We wrap the code in an async function (done above),
            # then get the function pointer and execute the function with the namespace.
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
            backtrace = traceback.format_exc()
            logger.error(f"Backtrace: {backtrace}")
            # Store full traceback for LLM feedback
            self.result.error_traceback = backtrace

        except Exception as e:
            self.result.runtime_error = e
            self.result.error_message = f"{type(e).__name__}: {e}"
            logger.error(f"Error executing code: {type(e).__name__}: {e}")
            backtrace = traceback.format_exc()
            logger.error(f"Backtrace: {backtrace}")
            # Store full traceback for LLM feedback
            self.result.error_traceback = backtrace

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

        # Check if this is a thinking step
        if hasattr(instruction_pointer, "step") and instruction_pointer.step == "TNK":
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

        This is called both for explicit Var() calls and for variable
        assignments like $x = 10 that are captured by LLMNamespace.

        Args:
            name: Variable name (without $ prefix, e.g., "x")
            value: Variable value
        """
        from playbooks.config import config

        # Check if value should be stored as an artifact (similar to playbook results)
        # Convert to artifact if value string representation exceeds threshold
        if len(str(value)) > config.artifact_result_threshold:
            # Create an artifact to store the large value
            artifact_summary = f"Variable: {name}"
            artifact_contents = str(value)

            artifact = Artifact(
                name=f"${name}",
                summary=artifact_summary,
                value=artifact_contents,
            )

            self.result.vars[name] = artifact

            # Update the actual state variables with $ prefix
            if self.agent.state and hasattr(self.agent.state, "variables"):
                self.agent.state.variables[f"${name}"] = artifact
        else:
            # Store as regular variable if below threshold
            self.result.vars[name] = value
            # Update the actual state variables with $ prefix
            if self.agent.state and hasattr(self.agent.state, "variables"):
                self.agent.state.variables.__setitem__(
                    name=f"${name}",
                    value=value,
                    instruction_pointer=self.current_instruction_pointer,
                )

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

        # Update state variables
        if self.agent.state and hasattr(self.agent.state, "variables"):
            self.agent.state.variables[f"${name}"] = artifact

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
        if self.agent.state and hasattr(self.agent.state, "variables"):
            self.agent.state.variables.__setitem__(
                name="$_",
                value=value,
                instruction_pointer=self.current_instruction_pointer,
            )
        self.result.playbook_finished = True

    async def _capture_yld(self, target: str = "user") -> None:
        """Capture Yld() call.

        Args:
            target: Yield target ("user", "human", agent_id, etc.)
        """
        target_lower = target.lower()

        if target_lower in ["user", "human"]:
            self.result.wait_for_user_input = True
            await self.agent.WaitForMessage("human")
        elif target_lower == "exit":
            self.result.exit_program = True
        elif target_lower == "return":
            self.result.playbook_finished = True
        else:
            # Agent ID or meeting spec
            self.result.wait_for_agent_input = True
            self.result.wait_for_agent_target = target
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
