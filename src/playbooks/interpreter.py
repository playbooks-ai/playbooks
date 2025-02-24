import json
import os
import re
from typing import TYPE_CHECKING, Any, Dict

import yaml

if TYPE_CHECKING:
    from .config import LLMConfig
    from .playbook import Playbook

from .call_stack import CallStack, CallStackFrame, InstructionPointer
from .enums import PlaybookExecutionType
from .llm_call import LLMCall
from .trace_mixin import TraceItem, TraceMixin, TraceWalker
from .types import AgentResponseChunk, ToolCall
from .utils.llm_helper import get_messages_for_prompt
from .variables import Variables


class StepExecution(TraceMixin):
    def __init__(
        self,
        step: str,
        metadata: Dict[str, Any] = None,
    ):
        super().__init__()
        self.step = step
        self.metadata = metadata

    def __repr__(self):
        return yaml.dump(self.metadata).strip()


class ToolExecutionResult(TraceItem):
    def __init__(self, message: str, tool_call: ToolCall):
        super().__init__(item=message, metadata={"tool_call": tool_call})
        self.tool_call = tool_call

    def __repr__(self):
        return self.tool_call.__repr__() + ": " + self.item


class ToolExecution(TraceMixin):
    def __init__(
        self,
        interpreter: "Interpreter",
        playbooks: Dict[str, "Playbook"],
        tool_call: ToolCall,
    ):
        super().__init__()
        self.interpreter = interpreter
        self.playbooks = playbooks
        self.tool_call = tool_call

    def execute(self):
        tool_call = self.tool_call
        # Look up an EXT playbook with the same name as the tool call
        ext_playbook = next(
            (
                p
                for p in self.playbooks.values()
                if p.execution_type == PlaybookExecutionType.EXT
                and p.klass == tool_call.fn
            ),
            None,
        )

        if ext_playbook is None:
            self.trace(
                ToolExecutionResult(
                    f"Error: {tool_call.fn} not found",
                    tool_call=tool_call,
                )
            )
            raise Exception(f"EXT playbook {tool_call.fn} not found")

        # If found, run the playbook
        func = ext_playbook.func
        retval = func(*tool_call.args, **tool_call.kwargs)
        self.trace(ToolExecutionResult(f"{retval}", tool_call=tool_call))
        tool_call.retval = retval
        yield AgentResponseChunk(tool_call=tool_call)

    def __repr__(self):
        return self.tool_call.__repr__()


class PlaybookExecution(TraceMixin):
    def __init__(
        self,
        interpreter,
        playbooks,
        current_playbook,
        instruction,
        llm_config=None,
        stream=False,
    ):
        super().__init__()
        self.interpreter: Interpreter = interpreter
        self.playbooks = playbooks
        self.current_playbook = current_playbook
        self.instruction = instruction
        self.llm_config = llm_config
        self.stream = stream
        self.wait_for_external_event: bool = False

    def execute(self):
        done = False
        while not done:
            self.trace(
                "Start iteration",
                metadata={
                    "playbook": self.current_playbook.klass,
                    "line_number": self.interpreter.call_stack.peek().instruction_pointer.line_number,
                    "instruction": self.instruction,
                },
            )
            interpreter_execution = InterpreterExecution(
                interpreter=self.interpreter,
                playbooks=self.playbooks,
                current_playbook=self.current_playbook,
                instruction=self.instruction,
                llm_config=self.llm_config,
                stream=self.stream,
            )
            self.trace(interpreter_execution)
            yield from interpreter_execution.execute()
            if interpreter_execution.wait_for_external_event:
                self.wait_for_external_event = True
                self.trace(
                    "Waiting for external event, exiting loop",
                )
                done = True

            if (
                self.interpreter.call_stack.peek().instruction_pointer.playbook
                != self.current_playbook.klass
            ):
                self.trace(
                    f"Switching to new playbook {self.interpreter.call_stack.peek().instruction_pointer.playbook}, exiting loop",
                )
                done = True

    def __repr__(self):
        return f"{self.current_playbook.klass}()"


class InterpreterExecution(TraceMixin):
    def __init__(
        self,
        interpreter: "Interpreter",
        playbooks: Dict[str, "Playbook"],
        current_playbook: "Playbook",
        instruction: str,
        llm_config: "LLMConfig" = None,
        stream: bool = False,
    ):
        super().__init__()
        self.interpreter: "Interpreter" = interpreter
        self.playbooks: Dict[str, "Playbook"] = playbooks
        self.current_playbook: "Playbook" = current_playbook
        self.instruction: str = instruction
        self.llm_config: "LLMConfig" = llm_config
        self.stream: bool = stream
        self.wait_for_external_event: bool = False

    def parse_response(self, response):
        # First try to extract yaml content between triple backticks
        yaml_match = re.search(r"```(?:yaml)?\n(.*?)```", response, re.DOTALL)
        if yaml_match:
            yaml_content = yaml_match.group(1)
        else:
            # If no triple backticks found, try to parse the entire response as YAML
            yaml_content = response

        try:
            parsed = yaml.safe_load(yaml_content)
            if not parsed or not isinstance(parsed, list):
                raise ValueError("Empty YAML content")
        except yaml.YAMLError as err:
            raise ValueError(f"Invalid YAML content: {yaml_content}") from err

        tool_calls = []
        last_executed_step = None
        updated_variables = {}

        abort_execution = False
        for step_dict in parsed:
            if abort_execution:
                break
            step = next(iter(step_dict))
            step = step.strip()
            step_execution = StepExecution(step, metadata=step_dict)
            self.trace(step_execution)

            last_executed_step = step
            step_trace = step_dict[step]

            # Sometimes llm returns a dict instead of a list, work around that
            if isinstance(step_trace, dict):
                step_trace = [{key: value} for key, value in step_trace.items()]

            for item in step_trace:
                if abort_execution:
                    break
                if "call" in item:
                    tool_calls.append(
                        ToolCall(
                            fn=item["call"]["fn"],
                            args=item["call"].get("args", []),
                            kwargs=item["call"].get("kwargs", {}),
                        )
                    )

                    if item["call"]["fn"] in self.playbooks:
                        # If this is a playbook call, ignore rest of the trace
                        # because we will execute the playbook now
                        if (
                            self.playbooks[item["call"]["fn"]].execution_type
                            == PlaybookExecutionType.INT
                        ):
                            abort_execution = True
                            break
                if "updated_vars" in item:
                    updated_variables.update(item["updated_vars"])

        return tool_calls, last_executed_step, updated_variables

    def execute(self):
        self.trace(
            "Start execution",
            metadata={
                "instruction": self.instruction,
                "current_playbook": self.current_playbook.klass,
                "session_context": self.interpreter.session_context(),
            },
        )

        done = False
        while not done:
            self.wait_for_external_event = False
            current_line_number = (
                self.interpreter.call_stack.peek().instruction_pointer.line_number
            )

            self.instruction = (
                f"\nResume at or after {self.current_playbook.klass}:{current_line_number} based on session log above.\n"
                + self.instruction
            )

            self.trace(
                "Start iteration",
                metadata={
                    "playbook": self.current_playbook.klass,
                    "line_number": current_line_number,
                    "instruction": self.instruction,
                },
            )
            prompt = self.interpreter.get_prompt(
                self.playbooks,
                self.current_playbook,
                self.instruction,
            )
            messages = get_messages_for_prompt(prompt)

            # Get response from LLM
            llm_call = LLMCall(
                llm_config=self.llm_config, messages=messages, stream=self.stream
            )
            self.trace(llm_call)
            response = []
            for chunk in llm_call.execute():
                response.append(chunk)
                yield AgentResponseChunk(raw=chunk)
                self.interpreter.process_chunk(chunk)

            yield AgentResponseChunk(raw="\n")

            # TODO: parse streaming response
            tool_calls, last_executed_step, updated_variables = self.parse_response(
                "".join(response)
            )

            self.trace(
                "LLM execution complete",
                metadata={
                    "tool_calls": tool_calls,
                    "last_executed_step": last_executed_step,
                    "updated_variables": updated_variables,
                },
            )
            # Process playbook calls and pass on external tool calls to agent thread
            self.instruction = ""
            playbook_calls = []
            missing_say_after_external_tool_call = False
            for tool_call in tool_calls:
                if tool_call.fn == "Say":
                    if tool_call.kwargs.get("waitForUserInput", False):
                        done = True
                        self.wait_for_external_event = True
                        self.trace(
                            "Waiting for user input, exiting loop",
                            metadata={"tool_call": tool_call},
                        )
                    missing_say_after_external_tool_call = False

                    yield AgentResponseChunk(tool_call=tool_call)
                elif tool_call.fn not in self.playbooks:
                    raise Exception(f"Playbook {tool_call.fn} not found")
                # if tool call is for a playbook, push it to the call stack
                elif (
                    self.playbooks[tool_call.fn].execution_type
                    == PlaybookExecutionType.INT
                ):
                    playbook_calls.append(tool_call.fn)
                    done = True
                    self.trace(
                        f"Need to execute playbook: {tool_call.fn}, exiting loop",
                        metadata={"tool_call": tool_call},
                    )
                # else pass on the external tool call to agent thread
                else:
                    done = True
                    tool_execution = ToolExecution(
                        interpreter=self.interpreter,
                        playbooks=self.playbooks,
                        tool_call=tool_call,
                    )
                    yield from tool_execution.execute()
                    self.trace(tool_execution)
                    self.trace(
                        "Exiting loop after executing tool call",
                        metadata={"tool_call": tool_call},
                    )
                    missing_say_after_external_tool_call = True

            # Update call stack
            (
                last_executed_step_pb,
                last_executed_step_ln,
                last_executed_step_type,
            ) = last_executed_step.split(":")

            if last_executed_step_type == "YLD":
                self.wait_for_external_event = True
                done = True
                self.trace(
                    "Waiting for external event on YLD, exiting loop",
                    metadata={"last_executed_step": last_executed_step},
                )

            # If there was no Say() after the last tool call,
            # we need to continue execution after the tool call
            if missing_say_after_external_tool_call:
                self.trace("No Say() after external tool call, continuing loop")
                done = False

            # Update call stack to reflect last executed step
            self.interpreter.call_stack.pop()
            self.interpreter.call_stack.push(
                CallStackFrame(
                    instruction_pointer=InstructionPointer(
                        playbook=last_executed_step_pb,
                        line_number=last_executed_step_ln,
                    ),
                    llm_chat_session_id=None,  # self.current_llm_session.llm_chat_session_id,
                )
            )

            # Update variables
            self.interpreter.manage_variables(updated_variables)

            # Any requests for playbook execution are pushed to the call stack
            if playbook_calls:
                for playbook_call in playbook_calls:
                    self.interpreter.call_stack.push(
                        CallStackFrame(
                            instruction_pointer=InstructionPointer(
                                playbook=playbook_call, line_number="01"
                            ),
                            llm_chat_session_id=None,
                        )
                    )
                assert done

    def __repr__(self):
        # Get list of playbook:line_number pairs from "Start iteration" trace items
        lines = []
        for item in self._trace_items:
            if item.item == "Start iteration":
                lines.append(
                    # item.metadata["playbook"]
                    # + ":"
                    item.metadata["line_number"]
                )
        return ", ".join(lines)


class Interpreter(TraceMixin):
    def __init__(self):
        super().__init__()
        self.local_variables = Variables()
        self.global_like_variables = Variables()
        self.call_stack = CallStack()
        self.yield_requested_on_say: bool = False

    def pop_from_call_stack(self):
        if self.call_stack:
            return self.call_stack.pop()
        return None

    def manage_variables(self, new_vars):
        # Update local variables
        for name, value in new_vars.items():
            self.local_variables.__setitem__(name, value, instruction_pointer=None)
        # Remove stale variables
        self.remove_stale_variables()

    def remove_stale_variables(self):
        # Logic to remove stale variables from local and global-like variables
        # This is a placeholder for the actual logic
        pass

    def integrate_trigger_matching(self):
        # Logic to integrate trigger matching when call stack is empty
        # This is a placeholder for the actual logic
        pass

    def execute(
        self,
        playbooks: Dict[str, "Playbook"],
        instruction: str,
        llm_config: dict = None,
        stream: bool = False,
    ):
        print(self.to_trace())
        # If call stack is empty, find initial playbook
        if self.call_stack.is_empty():
            # Find the first playbook whose trigger includes "BGN"
            current_playbook = [
                p
                for p in playbooks.values()
                if p.trigger and "BGN" in p.trigger["markdown"]
            ]
            current_playbook = next(iter(current_playbook), None)
            if not current_playbook:
                raise Exception("No initial playbook found")

            # Push the initial playbook to the call stack
            self.call_stack.push(
                CallStackFrame(
                    InstructionPointer(
                        playbook=current_playbook.klass,
                        line_number="01",
                    ),
                    llm_chat_session_id=None,
                )
            )

        done = False
        while not done:
            current_playbook = playbooks[
                self.call_stack.peek().instruction_pointer.playbook
            ]

            playbook_execution = PlaybookExecution(
                interpreter=self,
                playbooks=playbooks,
                current_playbook=current_playbook,
                instruction=instruction,
                llm_config=llm_config,
                stream=stream,
            )
            self.trace(playbook_execution)
            yield from playbook_execution.execute()
            if playbook_execution.wait_for_external_event:
                done = True

    def process_chunk(self, chunk):
        # Example processing logic for a chunk
        # print("Processing chunk:", chunk)
        # self.current_llm_session.process_chunk(chunk)
        # Here you can add logic to manage the call stack and variables based on the chunk
        # For now, just a placeholder
        pass

    def get_playbook_trigger_summary(self, playbook: "Playbook") -> str:
        strs = [f"- {playbook.signature}: {playbook.description}"]
        if playbook.trigger:
            strs.append(
                "\n".join(
                    [f"  - {t['markdown']}" for t in playbook.trigger["children"]]
                )
            )
        return "\n".join(strs)

    def get_prompt(
        self,
        playbooks: Dict[str, "Playbook"],
        current_playbook: "Playbook",
        instruction: str,
    ) -> str:
        playbooks_signatures = "\n".join(
            [
                self.get_playbook_trigger_summary(playbook)
                for playbook in playbooks.values()
            ]
        )
        current_playbook_markdown = playbooks[current_playbook.klass].markdown

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
                "initial_call_stack": self.call_stack.to_dict(),
                "initial_variables": self.local_variables.to_dict(),
            },
            indent=2,
        )

        prompt = prompt.replace("{{PLAYBOOKS_SIGNATURES}}", playbooks_signatures)
        prompt = prompt.replace(
            "{{CURRENT_PLAYBOOK_MARKDOWN}}", current_playbook_markdown
        )
        prompt = prompt.replace("{{SESSION_CONTEXT}}", self.session_context())
        prompt = prompt.replace("{{INITIAL_STATE}}", initial_state)
        prompt = prompt.replace("{{INSTRUCTION}}", instruction)

        return prompt

    def session_context(self):
        items = []
        TraceWalker.walk(
            self,
            lambda item: (
                items.append(item)
                if item.item.__class__.__name__
                in (
                    "StepExecution",
                    "MessageReceived",
                    "ToolExecutionResult",
                )
                else None
            ),
        )

        log = []
        for item in items:
            lines = item.item.__repr__().split("\n")
            log.append("- " + lines[0])
            if len(lines) > 1:
                for line in lines[1:]:
                    log.append("  " + line)
        return "\n".join(log)
