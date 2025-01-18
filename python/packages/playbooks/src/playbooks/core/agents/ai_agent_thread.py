from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from playbooks.core.agents.ai_agent import AIAgent
    from playbooks.core.runtime import PlaybooksRuntime

from playbooks.core.playbook import Playbook


class AIAgentThread:
    def __init__(self, agent: "AIAgent"):
        self.agent = agent

    def run(
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

        # Get response from LLM
        for chunk in runtime.get_llm_completion(messages=messages):
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
# Playbooks interpreter trace
## [Hello:1] Greet the user with welcome to the Agentic AI world
- Say("Hello, Welcome to the Agentic AI World!")

## [Hello:2] return positive message
- return "Awesome"
- Returning to [CallerHello:4]

## [CallerHello:5] Say the positive message
- Say("Awesome")
```

Example where execution is paused due to function call -
```
# Playbooks interpreter trace
## [Hello:1] Greet the user with welcome to the Agentic AI world
- Say("Hello, Welcome to the Agentic AI World!")

## [Hello:2] ask user for name
- Say("What is your name?")
- Paused at [Hello:2]
```

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

Built-in functions -
- Say($message): Send a message to the user
- FireEvent($event): Fire an event to another agent, e.g. FireEvent("Ask Validator agent if X Æ A-12 is a valid name")

External functions -
- GetWeather($location): Call an external function to get weather for a location, e.g. GetWeather("San Francisco")

```playbooks
{{playbooks}}
```
        """

        prompt = prompt.replace("{{playbooks}}", playbooks)

        return prompt
