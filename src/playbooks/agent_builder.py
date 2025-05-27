import ast
import inspect
import re
import types
from typing import Any, Callable, Dict, List, Optional, Type

from playbooks.event_bus import EventBus
from playbooks.markdown_playbook_execution import MarkdownPlaybookExecution

from .ai_agent import AIAgent
from .config import LLMConfig
from .exceptions import AgentConfigurationError
from .playbook import Playbook, PlaybookExecutionType, PlaybookTriggers
from .playbook_decorator import playbook_decorator
from .utils.markdown_to_ast import markdown_to_ast, refresh_markdown_attributes


class AgentBuilder:
    """
    Responsible for dynamically generating Agent classes from playbook AST.
    This class creates Agent classes based on the Abstract Syntax Tree
    representation of playbooks.
    """

    def __init__(self):
        """Initialize a new AgentBuilder instance."""
        self.playbooks = {}
        self.agent_python_namespace = {}

    @classmethod
    def create_agents_from_ast(cls, ast: Dict) -> Dict[str, Type[AIAgent]]:
        """
        Create agent classes from the AST representation of playbooks.

        Args:
            ast: AST dictionary containing playbook definitions

        Returns:
            Dict[str, Type[Agent]]: Dictionary mapping agent names to their classes
        """
        agents = {}
        for h1 in ast.get("children", []):
            if h1.get("type") == "h1":
                agent_name = h1["text"]
                builder = cls()
                h1["children"].extend(AgentBuilder._get_builtin_playbooks())
                agents[agent_name] = builder.create_agent_class_from_h1(h1)

        return agents

    def create_agent_class_from_h1(self, h1: Dict) -> Type[AIAgent]:
        """
        Create an Agent class from an H1 section in the AST.

        Args:
            h1: Dictionary representing an H1 section from the AST

        Returns:
            Type[Agent]: Dynamically created Agent class

        Raises:
            AgentConfigurationError: If agent configuration is invalid
        """
        klass = h1["text"]
        if not klass:
            raise AgentConfigurationError("Agent name is required")

        description = self._extract_description(h1)
        self.playbooks = {}
        self.agent_python_namespace = {}

        # Process all children nodes
        self._process_code_blocks(h1)
        self._process_markdown_playbooks(h1)

        if not self.playbooks:
            raise AgentConfigurationError(f"No playbooks defined for AI agent {klass}")

        # Refresh markdown attributes to ensure Python code is not sent to the LLM
        refresh_markdown_attributes(h1)

        # Create Agent class
        return self._create_agent_class(klass, description, h1)

    def _process_code_blocks(self, h1: Dict) -> None:
        """Process code blocks in the AST and extract playbooks."""
        for child in h1.get("children", []):
            if child.get("type") == "code-block":
                new_playbooks = self.playbooks_from_code_block(child["text"])
                self.playbooks.update(new_playbooks)

    def _process_markdown_playbooks(self, h1: Dict) -> None:
        """Process H2 sections in the AST and extract markdown playbooks."""
        for child in h1.get("children", []):
            if child.get("type") == "h2":
                playbook = Playbook.from_h2(child)
                self.playbooks[playbook.klass] = playbook
                wrapper = self.create_markdown_playbook_python_wrapper(playbook)
                playbook.func = wrapper
                playbook.func.__globals__.update(self.agent_python_namespace)

                def create_call_through_agent(agent_python_namespace, playbook):
                    def call_through_agent(*args, **kwargs):
                        return agent_python_namespace["agent"].execute_playbook(
                            playbook.klass, args, kwargs
                        )

                    return call_through_agent

                self.agent_python_namespace[playbook.klass] = create_call_through_agent(
                    self.agent_python_namespace, playbook
                )

    def _create_agent_class(
        self,
        klass: str,
        description: Optional[str],
        h1: Dict,
    ) -> Type[AIAgent]:
        """Create and return a new Agent class."""
        agent_class_name = self.make_agent_class_name(klass)

        # Check if class already exists
        if agent_class_name in globals():
            raise AgentConfigurationError(
                f'Agent class {agent_class_name} already exists for agent "{klass}"'
            )

        # Store references to playbooks and namespace for closure
        playbooks = self.playbooks
        source_line_number = h1.get("line_number")

        # Define __init__ for the new class
        def __init__(self, event_bus: EventBus):
            AIAgent.__init__(
                self,
                klass=klass,
                description=description,
                playbooks=playbooks,
                event_bus=event_bus,
                source_line_number=source_line_number,
            )

        # Create and return the new Agent class
        return type(
            agent_class_name,
            (AIAgent,),
            {
                "__init__": __init__,
            },
        )

    def playbooks_from_code_block(
        self,
        code_block: str,
    ) -> Dict[str, Playbook]:
        """
        Create playbooks from a code block.

        Args:
            code_block: Python code block string

        Returns:
            Dict[str, Playbook]: Discovered playbooks
        """
        # Set up the execution environment
        existing_keys = list(self.agent_python_namespace.keys())
        environment = self._prepare_execution_environment()
        self.agent_python_namespace.update(environment)

        # Execute the code block in the isolated namespace
        python_local_namespace = {}
        exec(code_block, self.agent_python_namespace, python_local_namespace)
        self.agent_python_namespace.update(python_local_namespace)

        # Get code for each function
        function_code = {}
        parsed_code = ast.parse(code_block)
        for item in parsed_code.body:
            if isinstance(item, ast.AsyncFunctionDef):
                function_code[item.name] = ast.unparse(item)

        # Discover all @playbook-decorated functions
        playbooks = self._discover_playbook_functions(existing_keys)

        # Add function code to playbooks
        for playbook in playbooks.values():
            playbook.code = function_code[playbook.klass]

        return playbooks

    def _prepare_execution_environment(self) -> Dict[str, Any]:
        """Prepare the execution environment for code blocks."""
        environment = {}

        environment.update(
            {
                "playbook": playbook_decorator,  # Inject decorator
                "__builtins__": __builtins__,  # Safe default
            }
        )

        return environment

    def _discover_playbook_functions(
        self, original_keys: List[str]
    ) -> Dict[str, Playbook]:
        """Discover playbook-decorated functions in the namespace."""
        playbooks = {}
        wrappers = {}

        for obj_name, obj in self.agent_python_namespace.items():
            if (
                isinstance(obj, types.FunctionType)
                and obj_name not in original_keys
                and getattr(obj, "__is_playbook__", False)
            ):
                # Create playbook from decorated function
                playbooks[obj.__name__] = self._create_playbook_from_function(obj)

                def create_call_through_agent(agent_python_namespace, playbook):
                    def call_through_agent(*args, **kwargs):
                        return agent_python_namespace["agent"].execute_playbook(
                            playbook.klass, args, kwargs
                        )

                    return call_through_agent

                wrappers[obj.__name__] = create_call_through_agent(
                    self.agent_python_namespace, playbooks[obj.__name__]
                )

        self.agent_python_namespace.update(wrappers)

        return playbooks

    @staticmethod
    def _create_playbook_from_function(func: Callable) -> Playbook:
        """Create a Playbook object from a decorated function."""
        sig = inspect.signature(func)
        signature = func.__name__ + str(sig)
        doc = inspect.getdoc(func)
        description = doc.split("\n")[0] if doc is not None else None
        triggers = getattr(func, "__triggers__", [])
        public = getattr(func, "__public__", False)
        # If triggers are not prefixed with T1:BGN, T1:CND, etc., add T{i}:CND
        # Use regex to find if prefix is missing
        triggers = [
            (
                f"T{i+1}:CND {trigger}"
                if not re.match(r"^T\d+:[A-Z]{3} ", trigger)
                else trigger
            )
            for i, trigger in enumerate(triggers)
        ]

        if triggers:
            triggers = PlaybookTriggers(
                playbook_klass=func.__name__,
                playbook_signature=signature,
                triggers=triggers,
            )
        else:
            triggers = None

        return Playbook(
            klass=func.__name__,
            execution_type=PlaybookExecutionType.CODE,
            signature=signature,
            triggers=triggers,
            func=func,
            description=description,
            steps=None,
            notes=None,
            code=None,
            markdown=None,
            public=public,
            source_line_number=None,  # Python functions don't have markdown line numbers
        )

    @staticmethod
    def create_markdown_playbook_python_wrapper(playbook: Playbook) -> Callable:
        """
        Create an async python function with the markdown playbook's name and
        inject the function into the agent_python_namespace.
        This will allow python playbooks to call markdown playbooks.

        Args:
            playbook: The markdown playbook to create a wrapper for

        Returns:
            An async wrapper function
        """

        async def wrapper(*args, **kwargs):
            # TODO: Implement actual wrapper logic to call markdown playbooks
            agent = playbook.func.__globals__["agent"]
            execution = MarkdownPlaybookExecution(agent, playbook.klass, LLMConfig())
            return await execution.execute(*args, **kwargs)

        return wrapper

    @staticmethod
    def _extract_description(h1: Dict) -> Optional[str]:
        """
        Extract description from H1 node.

        Args:
            h1: Dictionary representing an H1 section from the AST

        Returns:
            Optional[str]: description or None if no description
        """
        description_parts = []

        for child in h1.get("children", []):
            if child.get("type") == "paragraph":
                description_text = child.get("text", "").strip()
                if description_text:
                    description_parts.append(description_text)

        description = "\n".join(description_parts).strip() or None
        return description

    @staticmethod
    def make_agent_class_name(klass: str) -> str:
        """
        Convert a string to a valid CamelCase class name prefixed with "Agent".

        Args:
            klass: Input string to convert to class name

        Returns:
            str: CamelCase class name prefixed with "Agent"

        Example:
            Input:  "This    is my agent!"
            Output: "AgentThisIsMyAgent"
        """
        # Replace any non-alphanumeric characters with a single space
        cleaned = re.sub(r"[^A-Za-z0-9]+", " ", klass)

        # Split on whitespace and filter out empty strings
        words = [w for w in cleaned.split() if w]

        # Capitalize each word and join
        capitalized_words = [w.capitalize() for w in words]

        # Prefix with "Agent" and return
        return "Agent" + "".join(capitalized_words)

    @staticmethod
    def _get_builtin_playbooks():
        """Add Say() Python playbook that prints given message."""
        code_block = """
```python
@playbook
async def SendMessage(target_agent_id: str, message: str):
    await agent.SendMessage(target_agent_id, message)

@playbook
async def WaitForMessage(source_agent_id: str) -> str | None:
    return await agent.WaitForMessage(source_agent_id)

@playbook
async def Say(message: str):
    await SendMessage("human", message)

@playbook
async def SaveArtifact(artifact_name: str, artifact_summary: str, artifact_content: str):
    agent.state.artifacts.set(artifact_name, artifact_summary, artifact_content)

@playbook
async def LoadArtifact(artifact_name: str):
    return agent.state.artifacts[artifact_name]
```        
"""

        return markdown_to_ast(code_block)["children"]
