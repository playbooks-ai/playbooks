from typing import TYPE_CHECKING, Any, Dict, List, Optional

from playbooks.core.agents.base_agent import Agent
from playbooks.core.exceptions import (
    AgentAlreadyRunningError,
    AgentConfigurationError,
    AgentError,
)
from playbooks.core.playbooks import Playbook
from playbooks.enums import AgentType

if TYPE_CHECKING:
    from playbooks.core.runtime import PlaybooksRuntime


class AIAgent(Agent):
    """AI agent."""

    # static method factory that creates an AIAgent for
    # a given H1 header
    @classmethod
    def from_h1(cls, h1: Dict):
        """Create an AIAgent from an H1 AST node.

        Args:
            h1: Dictionary representing an H1 AST node
        """
        agent = cls(klass=h1["text"], description=h1.get("description", ""))
        agent.playbooks = [
            Playbook.from_h2(h2)
            for h2 in h1.get("children", [])
            if h2.get("type") == "h2"
        ]
        return agent

    def __init__(self, klass: str, description: str):
        super().__init__(klass, AgentType.AI)
        self.description = description
        self.playbooks: list[Playbook] = []
        self.main_thread: Optional[Any] = None

    async def run(self, runtime: "PlaybooksRuntime" = None):
        """Run the agent."""
        # raise custom exception AgentConfigurationError if no playbooks are defined
        if len(self.playbooks) == 0:
            raise AgentConfigurationError("No playbooks defined for AI agent")

        # raise custom exception AgentAlreadyRunningError if agent is already running
        if self.main_thread is not None:
            raise AgentAlreadyRunningError("AI agent is already running")

        # raise custom exception AgentError if runtime is not provided
        if runtime is None:
            raise AgentError("Runtime is not provided")

        # create self.main_thread of type AgentThread
        self.main_thread = AIAgentThread(self)

        # run the main thread
        # TODO: add support for filtering playbooks
        async for chunk in self.main_thread.run(
            runtime=runtime,
            included_playbooks=self.playbooks,
            instruction="Begin",
        ):
            yield chunk

    async def process_message(
        self,
        message: str,
        from_agent: "Agent",
        routing_type: str,
        runtime: "PlaybooksRuntime",
    ):
        # Process the message on main thread
        async for chunk in self.main_thread.run(
            runtime=runtime,
            included_playbooks=self.playbooks,
            instruction=f"Received the following message from {from_agent.klass}: {message}",
        ):
            yield chunk


class AIAgentThread:
    def __init__(self, agent: AIAgent):
        self.agent = agent

    async def run(
        self,
        runtime: "PlaybooksRuntime",
        included_playbooks: List[Playbook],
        instruction: str,
    ):
        # TODO: track and add conversation history
        messages = [
            {
                "role": "system",
                "content": self.get_system_prompt(included_playbooks),
            },
            {"role": "user", "content": instruction},
        ]

        async for chunk in runtime.get_llm_completion(messages=messages):
            yield chunk

    def get_system_prompt(self, include_playbooks: List["Playbook"]) -> str:
        playbooks = "\n".join([playbook.markdown for playbook in include_playbooks])

        prompt = """
You are a pseudocode interpreter. Faithfully execute provided pseudocode.
Pseudocode will be written as "playbooks", which are function-like objects written in markdown.

- The Agent name is H1
- The playbook name is H2
    - Trigger conditions for a playbook are in the "Triggers" H3
    - playbook steps are in the "Steps" H3
    - Special cases, validations, etc are in "Notes" H3

As you execute each line, output code on the line with instruction pointer, e.g. "[MyPlaybook:4] Say hello to the user", then explain how it was executed and then say what the result was. Do not output anything else.

For example, if call stack is [CallerHello:4] -
```
# Pseudocode interpreter trace
## [Hello:1] Greet the user with welcome to the Agentic AI world
- Say("Hello, Welcome to the Agentic AI World!")

## [Hello:2] return positive message
- Return("Awesome")
- Returning to [CallerHello:4]
```

Example where execution is paused due to function call -
```
# Pseudocode interpreter trace
## [Hello:1] Greet the user with welcome to the Agentic AI world
- Say("Hello, Welcome to the Agentic AI World!")

## [Hello:2] ask user for name
- Say("What is your name?")
- Paused at [Hello:2]
```

Built-in functions -
- Say($message): Send a message to the user
- Return($value): Return a value to the caller
- FireEvent($event): Fire an event to another agent

At the end of the execution, output the following -
```
{
"thread_id": current thread's id e.g. "main" or 123,
"variables": {list variable values that were modified e.g. "var3": 10},
"event_to_fire": [list any events to be fired, if any],
"paused_at": current instruction pointer e.g. "PlaybookOne:4" if paused, otherwise None,
"call_stack": if paused then call stack  e.g. [PlaybookOne:4, GoodPlaybook:2], otherwise [],
"call": python code for external function calls, if any, e.g. `ExternalFunction(param1=10, p2="hello")`
}
```

Handle any exceptions gracefully. If a generated playbook is failing at its task or isn't resilient against exceptions, you may regenerate an improved playbook and repeat processing.

```playbooks
{{playbooks}}
```
        """

        prompt = prompt.replace("{{playbooks}}", playbooks)

        return prompt
