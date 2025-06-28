import ast
import json
import re
from typing import Any, List

from playbooks.agents import LocalAIAgent
from playbooks.call_stack import InstructionPointer
from playbooks.event_bus import EventBus
from playbooks.playbook_call import PlaybookCall
from playbooks.utils.spec_utils import SpecUtils
from playbooks.variables import Variables


class LLMResponseLine:
    def __init__(self, text: str, event_bus: EventBus, agent: LocalAIAgent):
        self.text = text
        self.event_bus = event_bus
        self.agent = agent

        self.steps = []
        self.playbook_calls: List[PlaybookCall] = []
        self.playbook_finished = False
        self.wait_for_user_input = False
        self.wait_for_agent_input = False
        self.wait_for_agent_target = None  # Store the target for YLD
        self.exit_program = False
        self.return_value = None
        self.is_thinking = False
        self.vars = Variables(event_bus)
        self.parse_line(self.text)

    def parse_line(self, line: str):
        # Extract Step metadata, e.g., `Step["auth_step"]`
        steps = re.findall(r'`Step\["([^"]+)"\]`', self.text)

        if any(step.endswith(":TNK") for step in steps):
            self.is_thinking = True

        self.steps: List[InstructionPointer] = []
        for step in steps:
            ip = self.agent.parse_instruction_pointer(step)
            self.steps.append(ip)

        # Extract Var metadata, e.g., `Var[$user_email, "test@example.com"]` or `Var[$pin, 1234]`
        # Captures the variable name (with $) and its value, parsing the value as a Python expression
        var_matches = re.findall(r"`Var\[(\$[^,\]]+),\s*([^`]+)\]`", self.text)

        for var_name, var_value_str in var_matches:
            # Parse the value as a Python expression safely
            if var_value_str == "null":
                var_value_str = "None"
            parsed_value = self._parse_arg_value(var_value_str.strip())
            self.vars[var_name] = parsed_value

        # Extract Trigger metadata, e.g., `Trigger["user_auth_failed"]`
        self.triggers = re.findall(r'`Trigger\["([^"]+)"\]`', self.text)

        if re.search(r"\byld\s+for\s+return\b", self.text):
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
                self.return_value = expression
            elif expression.startswith('"') and expression.endswith('"'):
                self.return_value = expression[1:-1]
            else:
                self.return_value = json.loads(match.group(1))

        # Extract playbook calls enclosed in backticks.
        # e.g., `MyPlaybook(arg1, arg2, kwarg1="value")` or `Playbook(key1=$var1)`
        # or `MyPlaybook(10, "someval", kwarg1="value", kwarg2=$my_var)`
        playbook_call_matches = re.findall(
            r"\`(?:.*\W*\=\W*)?([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*\(.*?\))\`", self.text
        )

        for playbook_call in playbook_call_matches:
            self.playbook_calls.append(self._parse_playbook_call(playbook_call))

    def _parse_playbook_call(self, playbook_call: str) -> PlaybookCall:
        """Parse a playbook call using Python's AST parser.

        This method parses a playbook call string into a dictionary containing the playbook name,
        positional arguments, and keyword arguments, handling both literal values and variable
        references (starting with $).

        Args:
            playbook_call: The complete playbook call string (e.g., "MyTool(arg1, kwarg='val')").

        Returns:
            A dictionary containing:
                - playbook_name: The name of the playbook
                - args: List of positional arguments
                - kwargs: Dictionary of keyword arguments

        Raises:
            ValueError: If the parsed expression is not a playbook call.
            SyntaxError: If the playbook call string is not valid Python syntax.
        """
        # Create a valid Python expression by properly handling $variables
        # First, find all $variables and replace them with __substituted__ prefix
        expr = playbook_call
        # Handle keyword argument names by removing $ prefix
        expr = re.sub(r"\$([a-zA-Z_][a-zA-Z0-9_]*)\s*=", r"\1=", expr)
        # Handle remaining $variables by replacing with __substituted__ prefix
        for match in re.finditer(r"\$[a-zA-Z_][a-zA-Z0-9_]*", expr):
            var = match.group(0)
            expr = expr.replace(var, f"__substituted__{var[1:]}")

        # Parse the expression
        tree = ast.parse(expr, mode="eval")
        if not isinstance(tree.body, ast.Call):
            raise ValueError("Expected a playbook call")

        # Extract playbook name
        playbook_name = self._parse_playbook_name(tree.body)

        # Extract positional arguments
        args = []
        for arg in tree.body.args:
            if isinstance(arg, ast.Name) and "__substituted__" in arg.id:
                # Convert back to $variable format
                args.append(arg.id.replace("__substituted__", "$"))
            elif isinstance(arg, ast.Constant):
                if isinstance(arg.value, str) and "__substituted__" in arg.value:
                    args.append(arg.value.replace("__substituted__", "$"))
                else:
                    args.append(arg.value)
            else:
                args.append(ast.literal_eval(ast.unparse(arg)))

        # Extract keyword arguments
        kwargs = {}
        for keyword in tree.body.keywords:
            if (
                isinstance(keyword.value, ast.Name)
                and "__substituted__" in keyword.value.id
            ):
                # Convert back to $variable format
                kwargs[keyword.arg] = keyword.value.id.replace("__substituted__", "$")
            elif isinstance(keyword.value, ast.Constant):
                if "__substituted__" in str(keyword.value.value):
                    kwargs[keyword.arg] = keyword.value.value.replace(
                        "__substituted__", "$"
                    )
                else:
                    kwargs[keyword.arg] = keyword.value.value
            else:
                kwargs[keyword.arg] = ast.literal_eval(ast.unparse(keyword.value))

        return PlaybookCall(playbook_name, args, kwargs)

    def _parse_playbook_name(self, call_node: ast.Call) -> str:
        """Parse a playbook name.

        This method parses a playbook name string into a dictionary containing the playbook name,
        positional arguments, and keyword arguments, handling both literal values and variable
        references (starting with $).
        """
        func = call_node.func

        # Reconstruct the full function name from attribute chain
        parts = []
        current = func

        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value

        if isinstance(current, ast.Name):
            parts.append(current.id)

        # Reverse to get correct order
        parts.reverse()
        return ".".join(parts)

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
            return ast.literal_eval(arg_value)
        except (ValueError, SyntaxError):
            # If literal_eval fails, return as is
            return arg_value

    def _parse_yld_patterns(self):
        """Parse YLD patterns and set appropriate wait flags."""
        text = self.text.lower()

        # YLD for user
        if re.search(r"\byld\s+for\s+user\b", text):
            self.wait_for_user_input = True
            return

        # YLD for Human
        if re.search(r"\byld\s+for\s+human\b", text):
            self.wait_for_user_input = True
            return

        # YLD for meeting (Phase 5+)
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

        # YLD for <agent_type>
        agent_type_match = re.search(
            r"\byld\s+for\s+([a-zA-Z][a-zA-Z0-9_]*(?:agent|Agent)?)\b", text
        )
        if agent_type_match:
            agent_type = agent_type_match.group(1)
            # Skip common words that aren't agent types
            if agent_type.lower() not in [
                "meeting",
                "user",
                "human",
                "agent",
                "return",
                "exit",
            ]:
                self.wait_for_agent_input = True
                self.wait_for_agent_target = agent_type
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
