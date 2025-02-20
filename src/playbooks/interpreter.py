import json
import os
import re
from typing import TYPE_CHECKING, List

import yaml

from .types import AgentResponseChunk, ToolCall
from .utils.llm_helper import get_completion, get_messages_for_prompt

if TYPE_CHECKING:
    from .playbook import Playbook


class Interpreter:
    def __init__(self):
        self.trace = []
        self.variables = {}
        self.call_stack = []
        self.available_external_functions = []
        self.yield_requested_on_say = False

    def run(
        self,
        included_playbooks: List["Playbook"],
        instruction: str,
        session_context: str,
        llm_config: dict = None,
        stream: bool = False,
    ):
        print("*" * 20)
        print("Interpreter.run()")
        print("session_context:", session_context)
        print("instruction:", instruction)

        # Update available_external_functions from EXT playbooks
        self.available_external_functions = []
        for playbook in included_playbooks:
            if playbook.execution_type == "EXT":
                self.available_external_functions.append(
                    playbook.signature + ": " + playbook.description
                )

        prompt = self.get_prompt(included_playbooks, session_context, instruction)
        messages = get_messages_for_prompt(prompt)

        # Get response from LLM
        response = []
        for chunk in get_completion(
            llm_config=llm_config, messages=messages, stream=stream
        ):
            if chunk is not None:
                response.append(chunk)
                yield AgentResponseChunk(raw=chunk)

        yield AgentResponseChunk(raw="\n")

        # TODO: parse streaming response
        tool_calls = self.parse_response("".join(response))
        for tool_call in tool_calls:
            yield AgentResponseChunk(tool_call=tool_call)

    def parse_response(self, response):
        # First try to extract yaml content between triple backticks
        yaml_match = re.search(r"```yaml\n(.*?)```", response, re.DOTALL)
        if yaml_match:
            yaml_content = yaml_match.group(1)
        else:
            # If no triple backticks found, try to parse the entire response as YAML
            yaml_content = response

        try:
            parsed = yaml.safe_load(yaml_content)
            if not parsed or not isinstance(parsed, dict):
                raise ValueError("Empty YAML content")
        except yaml.YAMLError as err:
            raise ValueError(f"Invalid YAML content: {yaml_content}") from err

        # Initialize tool calls list
        tool_calls = []

        # Store trace and collect function calls
        self.trace.extend(parsed["trace"])
        self.yield_requested_on_say = False
        for step in parsed["trace"]:
            if "ext" in step and "result" not in step:
                ext = step["ext"]
                if isinstance(ext, dict):
                    ext = [ext]
                for e in ext:
                    tool_calls.append(
                        ToolCall(
                            fn=e["fn"],
                            args=e.get("args", []),
                            kwargs=e.get("kwargs", {}),
                        )
                    )

                    if "yield" in step and e["fn"] == "Say":
                        self.yield_requested_on_say = (
                            self.yield_requested_on_say or step["yield"]
                        )

        # Update final state
        self.call_stack = parsed["stack"]

        if "vars" in parsed:
            self.variables.update(parsed["vars"])

        return tool_calls

    def get_prompt(
        self,
        included_playbooks: List["Playbook"],
        session_context: str,
        instruction: str,
    ) -> str:
        playbooks = "\n".join([playbook.markdown for playbook in included_playbooks])

        prompt = open(
            os.path.join(os.path.dirname(__file__), "prompts/interpreter_run.txt"),
            "r",
        ).read()

        # initial_state =
        # {
        #     "thread_id": "main",
        #     "initial_call_stack": [CheckOrderStatusMain:01.01, AuthenticateUserPlaybook:03],
        #     "initial_variables": {
        #       "$isAuthenticated": false,
        #       "$email": abc7873@yahoo.com,
        #       "$pin": 8989
        #       "$authToken": null
        #     },
        #     "available_external_functions": [
        #         "Say($message) -> None: Say something to the user",
        #         "Handoff() -> None: Connects the user to a human",
        #     ]
        # }
        initial_state = json.dumps(
            {
                "thread_id": "main",
                "initial_call_stack": self.call_stack,
                "initial_variables": self.variables,
                "available_external_functions": self.available_external_functions,
            },
            indent=2,
        )

        prompt = prompt.replace("{{PLAYBOOKS_CONTENT}}", playbooks)
        prompt = prompt.replace("{{SESSION_CONTEXT}}", session_context)
        prompt = prompt.replace("{{INITIAL_STATE}}", initial_state)
        prompt = prompt.replace("{{INSTRUCTION}}", instruction)

        return prompt
