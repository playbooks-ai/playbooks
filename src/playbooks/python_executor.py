"""Python code executor with controlled namespace and capture functions.

This module provides execution of LLM-generated Python code with injected
capture functions (Step, Say, Var, etc.) that record directives.
"""

import asyncio
import logging
import traceback
import types
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from playbooks.agent_proxy import create_agent_proxies, create_playbook_wrapper
from playbooks.call_stack import InstructionPointer
from playbooks.debug.debug_handler import NoOpDebugHandler
from playbooks.llm_messages.types import ArtifactLLMMessage
from playbooks.playbook_call import PlaybookCall
from playbooks.utils.inject_setvar import inject_setvar
from playbooks.utils.spec_utils import SpecUtils
from playbooks.variables import Artifact

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
                from .variables import Variable

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
    """Result of executing Python code with capture functions."""

    def __init__(self):
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


class PythonExecutor:
    """Executes Python code with controlled namespace and capture functions."""

    def __init__(self, agent: "LocalAIAgent"):
        """Initialize Python executor.

        Args:
            agent: The AI agent executing the code
            state: The execution state (contains variables, etc.)
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

    def build_namespace(self, playbook_args: dict = None) -> LLMNamespace:
        """Build namespace with injected capture functions.

        Args:
            playbook_args: Optional dict of playbook argument names to values

        Returns:
            LLMNamespace containing:
            - Capture functions (Step, Say, Var, etc.)
            - Playbook call functions from registry
            - Agent proxy objects for cross-agent calls
            - Existing variables from state
            - Playbook arguments (if provided)
        """
        namespace = LLMNamespace(
            self,
            {
                # **self.agent.namespace_manager.namespace,
                "Step": self._capture_step,
                "Say": self._capture_say,
                "Var": self._capture_var,
                "Artifact": self._capture_artifact,
                "Trigger": self._capture_trigger,
                "Return": self._capture_return,
                "Yld": self._capture_yld,
            },
        )

        # Add playbook functions from registry
        # Use dict.__setitem__ to bypass namespace interception
        # so playbook names don't get captured as variables
        if hasattr(self.agent, "playbooks"):
            for playbook_name, playbook in self.agent.playbooks.items():
                # Special handling for Say() to check if already streamed
                if playbook_name == "Say":
                    dict.__setitem__(
                        namespace,
                        playbook_name,
                        self._create_say_wrapper(),
                    )
                else:
                    dict.__setitem__(
                        namespace,
                        playbook_name,
                        create_playbook_wrapper(
                            playbook_name=playbook_name,
                            current_agent=self.agent,
                            namespace=namespace,
                        ),
                    )

        # Add agent proxies for cross-agent playbook calls
        # Use dict.__setitem__ to bypass interception
        agent_proxies = create_agent_proxies(self.agent, namespace)
        for agent_name, proxy in agent_proxies.items():
            dict.__setitem__(namespace, agent_name, proxy)

        # Add existing variables from state
        # Use dict.__setitem__ to bypass interception so these don't get
        # captured as new assignments
        if self.agent.state and hasattr(self.agent.state, "variables"):
            for var_name, var_value in self.agent.state.variables.to_dict().items():
                # Strip $ prefix from variable names for the namespace
                clean_name = var_name[1:] if var_name.startswith("$") else var_name
                dict.__setitem__(namespace, clean_name, var_value)

        dict.__setitem__(namespace, "asyncio", asyncio)

        # Add builtins with dangerous ones removed
        # Start with all builtins, then remove the most dangerous operations
        # This gives LLMs flexibility while maintaining some safety guardrails
        import builtins

        blocked_builtins = {
            "eval",  # Can execute arbitrary code
            "exec",  # Can execute arbitrary code
            "compile",  # Can compile arbitrary code
            "__import__",  # Can import arbitrary modules
            "open",  # Can read/write arbitrary files
            "input",  # Can block execution waiting for stdin
            "breakpoint",  # Debugger access
            "exit",  # Can terminate the process
            "quit",  # Can terminate the process
            "help",  # Interactive help system
            "license",  # Not needed
            "copyright",  # Not needed
            "credits",  # Not needed
        }

        for name in dir(builtins):
            if not name.startswith("_") and name not in blocked_builtins:
                dict.__setitem__(namespace, name, getattr(builtins, name))

        # Add playbook arguments to namespace
        # Use dict.__setitem__ to bypass interception so these don't get
        # captured as new assignments
        if playbook_args:
            for arg_name, arg_value in playbook_args.items():
                dict.__setitem__(namespace, arg_name, arg_value)

        return namespace

    async def execute(self, code: str, playbook_args: dict = None) -> ExecutionResult:
        """Execute Python code and return captured results.

        Args:
            code: Python code to execute (may contain $var = value syntax)
            playbook_args: Optional dict of playbook argument names to values

        Returns:
            ExecutionResult containing captured directives and any errors

        Raises:
            Does not raise - all errors are captured in result.error_message
        """
        self.result = ExecutionResult()

        try:
            # Pre-process code to handle $variable syntax
            # Convert $variable → variable so the code is valid Python
            from playbooks.utils.expression_engine import preprocess_program

            code = preprocess_program(code)

            # Build namespace with capture functions
            namespace = self.build_namespace(playbook_args=playbook_args)

            # Wrap in async function, then inject Var() calls
            # These can raise SyntaxError if the code has syntax issues
            try:
                # Wrap code in async function for execution first
                indented_lines = [f"    {line}" for line in code.splitlines()]
                indented_code = "\n".join(indented_lines)
                code = f"""async def __async_exec__():
{indented_code}
"""
                # Now inject SetVar calls (works on function bodies)
                code = inject_setvar(code)
            except SyntaxError as e:
                self.result.syntax_error = e
                self.result.error_message = f"SyntaxError: {e}"
                logger.error(f"Syntax error during preprocessing: {e}")
                raise

            # Compile code to check for syntax errors early
            try:
                compiled_code = compile(code, "<llm>", "exec")
            except SyntaxError as e:
                self.result.syntax_error = e
                self.result.error_message = f"SyntaxError: {e}"
                logger.error(f"Syntax error executing code: {e}")
                raise

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
            raise

        except Exception as e:
            self.result.runtime_error = e
            self.result.error_message = f"{type(e).__name__}: {e}"
            logger.error(f"Error executing code: {type(e).__name__}: {e}")
            backtrace = traceback.format_exc()
            logger.error(f"Backtrace: {backtrace}")
            raise

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
                if SpecUtils.is_meeting_spec(target_agent_id):
                    meeting_id = SpecUtils.extract_meeting_id(target_agent_id)
                    if meeting_id == "current":
                        meeting_id = self.agent.state.call_stack.peek().meeting_id
                    await self.agent.WaitForMessage(f"meeting {meeting_id}")
                else:
                    await self.agent.WaitForMessage(target_agent_id)

    def _resolve_yld_target(self, target: str) -> str:
        """Resolve a YLD target to an agent ID.

        Args:
            target: The YLD target specification

        Returns:
            Resolved agent ID or None if target couldn't be resolved
        """
        if not target:
            return None

        # Use the unified target resolver with no fallback for YLD
        # (YLD should be explicit about what it's waiting for)
        return self.agent.resolve_target(target, allow_fallback=False)

    def _create_say_wrapper(self):
        """Create a wrapper for Say() that ensures proper pre/post processing.

        The wrapper calls execute_playbook to ensure proper logging, langfuse tracking,
        and other pre/post processing. The _currently_streaming flag is checked
        internally by agent.Say() to prevent duplicate output.
        """

        async def say_wrapper(target: str, message: str):
            # Execute the Say() playbook (which will internally check _currently_streaming)
            success, result = await self.agent.execute_playbook(
                "Say", [target, message], {}
            )
            if not success:
                return "ERROR: " + result
            return result

        return say_wrapper
