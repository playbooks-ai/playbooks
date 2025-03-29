import json
import os
from typing import Dict, List, Optional

from playbooks.interpreter.execution_state import ExecutionState
from playbooks.playbook import Playbook
from playbooks.utils.llm_helper import get_messages_for_prompt


class InterpreterPrompt:
    """Generates the prompt for the interpreter LLM based on the current state."""

    def __init__(
        self,
        state: ExecutionState,
        playbooks: Dict[str, Playbook],
        current_playbook: Optional[Playbook],
        instruction: str,
        agent_instructions: str,
    ):
        """
        Initializes the InterpreterPrompt.

        Args:
            state: The current execution state.
            playbooks: A dictionary of available playbooks.
            current_playbook: The currently executing playbook, if any.
            instruction: The user's latest instruction.
            agent_instructions: General instructions for the agent.
        """
        self.state = state
        self.playbooks = playbooks
        self.current_playbook = current_playbook
        self.instruction = instruction
        self.agent_instructions = agent_instructions

    @property
    def prompt(self) -> str:
        """Constructs the full prompt string for the LLM.

        Returns:
            The formatted prompt string.
        """
        trigger_instructions = []
        for playbook in self.playbooks.values():
            trigger_instructions.extend(playbook.trigger_instructions())
        trigger_instructions_str = "\n".join(trigger_instructions)

        current_playbook_markdown = (
            self.playbooks[self.current_playbook.klass].markdown
            if self.current_playbook
            else "No playbook is currently running."
        )

        try:
            with open(
                os.path.join(
                    os.path.dirname(__file__), "../prompts/interpreter_run.txt"
                ),
                "r",
            ) as f:
                prompt_template = f.read()
        except FileNotFoundError:
            print("Error: Prompt template file not found!")
            return "Error: Prompt template missing."

        initial_state = json.dumps(
            {
                "call_stack": self.state.call_stack.to_dict(),
                "state": self.state.variables.to_dict(),
            },
            indent=2,
        )

        conversation_history_str = "\n".join(self.state.conversation_history)

        prompt = prompt_template.replace("{{TRIGGERS}}", trigger_instructions_str)
        prompt = prompt.replace(
            "{{CURRENT_PLAYBOOK_MARKDOWN}}", current_playbook_markdown
        )
        prompt = prompt.replace("{{CONVERSATION_HISTORY}}", conversation_history_str)
        prompt = prompt.replace("{{INITIAL_STATE}}", initial_state)
        prompt = prompt.replace("{{INSTRUCTION}}", self.instruction)
        prompt = prompt.replace("{{AGENT_INSTRUCTIONS}}", self.agent_instructions)
        return prompt

    @property
    def messages(self) -> List[Dict[str, str]]:
        """Formats the prompt into the message structure expected by the LLM helper."""
        return get_messages_for_prompt(self.prompt)
