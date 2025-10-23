import ast
import json
import re
from typing import TYPE_CHECKING, Any, List

from simpleeval import FeatureNotAvailable, NameNotDefined, simple_eval

from playbooks.call_stack import InstructionPointer
from playbooks.event_bus import EventBus
from playbooks.playbook_call import PlaybookCall
from playbooks.utils.async_init_mixin import AsyncInitMixin
from playbooks.utils.spec_utils import SpecUtils
from playbooks.variables import Artifact, Variables

from .utils.expression_engine import ExpressionContext, parse_playbook_call

if TYPE_CHECKING:
    from playbooks.agents import LocalAIAgent


class LLMResponseLine(AsyncInitMixin):
    def __init__(self, text: str, event_bus: EventBus, agent: "LocalAIAgent"):
        super().__init__()
        self.text = text
        self.event_bus = event_bus
        self.agent = agent

        self.steps: List[InstructionPointer] = []
        self.playbook_calls: List[PlaybookCall] = []
        self.playbook_finished = False
        self.wait_for_user_input = False
        self.wait_for_agent_input = False
        self.wait_for_agent_target = None  # Store the target for YLD
        self.exit_program = False
        self.return_value = None
        self.is_thinking = False
        self.vars = Variables(event_bus, agent.id)

        self.expression_context = ExpressionContext(agent, agent.state, None)

    async def _async_init(self):
        await self.parse_line()

    async def parse_line(self):
        # Extract Step metadata, e.g., `Step["auth_step"]`
        steps = re.findall(r'`Step\["([^"]+)"\]`', self.text)

        if any(step.endswith(":TNK") for step in steps):
            self.is_thinking = True

        self.steps: List[InstructionPointer] = []
        for step in steps:
            self.steps.append(self.agent.parse_instruction_pointer(step))

        # Extract Artifact metadata: `Artifact[$name, "summary", """content"""]`
        artifact_matches = re.findall(
            r'`Artifact\[(\$[^,\]]+),\s*"([^"]+)",\s*"""(.*?)"""\]`',
            self.text,
            re.DOTALL,
        )

        for var_name, summary, content in artifact_matches:
            # Create Artifact object
            artifact_name = (
                var_name[1:] if var_name.startswith("$") else var_name
            )  # Remove $ prefix for artifact name
            artifact = Artifact(name=artifact_name, summary=summary, value=content)
            self.vars[var_name] = artifact

        # Extract Var metadata: `Var[$user_email, "test@example.com"]` or `Var[$pin, 1234]`
        # Now supports multi-line strings: `Var[$text, """multi\nline"""]`
        # First, try to match triple-quoted strings
        var_multiline_matches = re.findall(
            r'`Var\[(\$[^,\]]+),\s*"""(.*?)"""\]`', self.text, re.DOTALL
        )

        for var_name, var_value in var_multiline_matches:
            # Skip if this was already processed as an artifact
            if var_name in self.vars:
                continue
            # Store the multi-line string as-is
            self.vars[var_name] = var_value

        # Then check for regular variable syntax
        # Use DOTALL to match multi-line content (e.g., JSON arrays/objects)
        var_matches = re.findall(r"`Var\[(\$[^,]+?),\s*(.*?)\]`", self.text, re.DOTALL)

        for var_name, var_value_str in var_matches:
            # Skip if this was already processed as an artifact or multi-line string
            if var_name in self.vars:
                continue

            # Skip if this looks like a triple-quoted string (will be handled by multiline matcher)
            if var_value_str.strip().startswith('"""'):
                continue

            # Parse the value as a Python expression safely
            if var_value_str == "null":
                var_value_str = "None"
            parsed_value = self._parse_arg_value(var_value_str.strip())

            # If parsed_value is a variable reference or expression (starts with $), evaluate it
            if isinstance(parsed_value, str) and parsed_value.startswith("$"):
                try:
                    # Try to evaluate as an expression (handles both simple vars and expressions)
                    resolved_value = self.expression_context.evaluate_expression(
                        parsed_value
                    )
                    self.vars[var_name] = resolved_value
                except Exception:
                    # Evaluation failed, store as-is (will error later if used)
                    self.vars[var_name] = parsed_value
            else:
                self.vars[var_name] = parsed_value

        # Extract Trigger metadata, e.g., `Trigger["user_auth_failed"]`
        self.triggers = re.findall(r'`Trigger\["([^"]+)"\]`', self.text)

        if re.search(r"`Return\[", self.text):
            self.playbook_finished = True

        if re.search(r"\byld\s+for\s+exit\b", self.text):
            self.exit_program = True

        # Handle YLD patterns
        self._parse_yld_patterns()

        # detect if return value in backticks somewhere in the line using regex
        match = re.search(r"`Return\[(.*?)\]`", self.text)
        literal_map = {
            "true": True,
            "false": False,
            "null": None,
        }
        if match:
            expression = match.group(1)
            if expression == "":
                self.return_value = None
            elif expression in literal_map.keys():
                self.return_value = literal_map[expression]
            elif expression.startswith("$"):
                # Store variable references/expressions for later evaluation
                self.return_value = expression
            elif expression.startswith('"') and expression.endswith('"'):
                self.return_value = expression[1:-1]
            else:
                self.return_value = self.expression_context.evaluate_expression(
                    match.group(1)
                )

        # Extract playbook calls enclosed in backticks.
        # e.g., `MyPlaybook(arg1, arg2, kwarg1="value")` or `Playbook(key1=$var1)`
        # or `MyPlaybook(10, "someval", kwarg1="value", kwarg2=$my_var)`
        # or with variable assignment: `$result:bool = MyPlaybook(arg1)`
        # or with multi-line strings: `Say("user", """multi\nline""")`
        playbook_call_matches = re.findall(
            r"\`(?:(\$[a-zA-Z_][a-zA-Z0-9_]*)(?::([a-zA-Z_][a-zA-Z0-9_]*))?\s*=\s*)?([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*\(.*?\))\`",
            self.text,
            re.DOTALL,
        )

        for match in playbook_call_matches:
            variable_to_assign = match[0] if match[0] else None
            type_annotation = match[1] if match[1] else None
            playbook_call_str = match[2]
            self.playbook_calls.append(
                parse_playbook_call(
                    playbook_call_str,
                    variable_to_assign=variable_to_assign,
                    type_annotation=type_annotation,
                )
            )

    def _parse_arg_value(self, arg_value: str) -> Any:
        """Parse an argument value to the appropriate type.

        This method converts string representations of values to their appropriate Python types,
        handling strings, numbers, booleans, None, and variable references.

        Args:
            arg_value: The string representation of the argument value.

        Returns:
            The parsed value with the appropriate type.
        """
        # If it starts with $, it's a variable reference
        if arg_value.startswith("$"):
            return arg_value

        # Try to parse as a Python literal using ast.literal_eval
        try:
            return simple_eval(arg_value)
        except (ValueError, SyntaxError, FeatureNotAvailable, NameNotDefined):
            try:
                return ast.literal_eval(arg_value)
            except (ValueError, SyntaxError):
                try:
                    return json.loads(arg_value)
                except (ValueError, SyntaxError):
                    return arg_value

    def _parse_yld_patterns(self):
        """Parse YLD patterns and set appropriate wait flags."""
        text = self.text.lower()

        # On this line, agent was thinking whether to yield. Actual call to yld would be on the next line.
        if text.startswith("yld?"):
            return

        # YLD for user
        if re.search(r"\byld\s+for\s+user\b", text):
            self.wait_for_user_input = True
            return

        # YLD for Human
        if re.search(r"\byld\s+for\s+human\b", text):
            self.wait_for_user_input = True
            return

        # YLD for meeting
        meeting_match = re.search(r"\byld\s+for\s+meeting(?:\s+(\d+))?\b", text)
        if meeting_match:
            meeting_id = meeting_match.group(1) if meeting_match.group(1) else "current"
            self.wait_for_agent_input = True
            self.wait_for_agent_target = SpecUtils.to_meeting_spec(meeting_id)
            return

        # YLD for agent <id>
        agent_id_match = re.search(r"\byld\s+for\s+agent\s+(\w+)\b", text)
        if agent_id_match:
            agent_id = agent_id_match.group(1)
            self.wait_for_agent_input = True
            self.wait_for_agent_target = agent_id
            return

        # YLD for <yld_type>
        yld_type_match = re.search(
            r"\byld\s+for\s+([a-zA-Z][a-zA-Z0-9_]*(?:agent|Agent)?)\b", text
        )
        if yld_type_match:
            yld_type = yld_type_match.group(1)
            # Skip common words that aren't agent types
            if yld_type.lower() not in [
                "meeting",
                "user",
                "human",
                "agent",
                "return",
                "exit",
            ]:
                self.wait_for_agent_input = True
                self.wait_for_agent_target = yld_type
                return

        # YLD for agent (last 1:1 non-human target)
        if re.search(r"\byld\s+for\s+agent\b", text):
            self.wait_for_agent_input = True
            self.wait_for_agent_target = "last_non_human_agent"
            return

        # YLD for call (yields for completion of a playbook call)
        if re.search(r"\byld\s+for\s+call\b", text):
            # For now, treat as equivalent to waiting for playbook completion
            # This might need more sophisticated handling in the future
            pass

        # yld for return
        if re.search(r"\byld\s+for\s+return\b", text):
            self.playbook_finished = True
            return
