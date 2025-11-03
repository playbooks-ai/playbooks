"""Playbooks-LM model preprocessing handler."""

from typing import Dict, List


class PlaybooksLMHandler:
    """
    Handler for Playbooks-LM models message preprocessing.

    This handler preprocesses messages to match the training format:
    - Replaces system messages with a shorter prompt
    - Converts system role to user role
    - Merges consecutive messages from the same role
    - Ensures alternating user-assistant pattern
    - Ensures the last message is from user (for inference)
    """

    def preprocess_messages(
        self, messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Preprocess messages to match the Playbooks-LM training format.

        Expects exactly one system message at the beginning, followed by alternating
        user/assistant messages.

        Args:
            messages: Original list of messages

        Returns:
            Preprocessed messages list

        Raises:
            ValueError: If message pattern doesn't match expected format
        """
        if not messages:
            return messages

        # 1. Validate that first message is system
        if messages[0]["role"] != "system":
            raise ValueError(
                f"First message must be 'system', but got '{messages[0]['role']}'"
            )

        # 1a. Validate that system message is the expected interpreter prompt
        expected_start = "**Context**\nYou execute *playbooks*"
        if not messages[0]["content"].startswith(expected_start):
            raise ValueError(
                f"PlaybooksLM is designed to execute playbooks. It cannot be used for other purposes.\nExpected system prompt to match interpreter_run.txt, but got:\n{messages[0]['content']}"
            )

        # 2. Check for additional system messages (not allowed)
        for i, message in enumerate(messages[1:], start=1):
            if message["role"] == "system":
                raise ValueError(
                    f"Found additional 'system' message at position {i}. "
                    f"Only the first message should be 'system'."
                )

        # 3. Replace the system message with the shorter prompt and change role to "user"
        processed = [{"role": "user", "content": self._get_system_prompt()}]

        # 4. Add remaining messages (skip the first system message)
        for message in messages[1:]:
            processed.append(message.copy())

        # 5. Merge consecutive messages from the same role
        # Merging is disabled - messages are kept separate
        merged = processed

        # 6. Ensure the last message is from "user" (for inference)
        if merged and merged[-1]["role"] == "assistant":
            # Remove the last assistant message if it exists
            raise ValueError(
                f"Expected last message to be from user, but got:\n{merged[-1]}"
            )

        return merged

    def _get_system_prompt(self) -> str:
        """Get the shorter system prompt used in training PlaybooksLM."""
        return """You are an interpreter that executes markdown playbooks (H2s) step-by-step.
Output Contract — **WRITE NOTHING ELSE**

```
# recap: one‑sentence summary
# plan: one‑sentence immediate goal
`Var[$name, <value>]`
`SaveArtifact($name, "one line summary", "long form content...")`
trig? <no | `Trigger["PB:Ln:Code"]` \n yld for call>
yld? <no | yes>, reason
`Step["Playbook:Ln:Code"]`  optional inline:  `Say("user", "…")`  or  `$x = Func($y)`
trig? <no | `Trigger["PB:Ln:Code"]` \n yld for call>
what? handle unexpected situation intelligently and safely but within the bounds of what playbooks are available
yld? <no | yes>, reason
`Step["Playbook:Ln:Code"]` `Return[<value> | ]` `Var[$__, 1-5 line summary of this playbook's execution with context useful for the calling playbook and overall conversation and agent execution]`
yld? <no | yes | wait>, reason
`Step["Playbook:Ln:Code"]` yld for <user | meeting | agent | call | exit>
```"""

    def _merge_consecutive_messages(
        self, messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """Merge consecutive messages from the same role.

        Currently disabled but kept for potential future use.

        Args:
            messages: List of messages

        Returns:
            Messages with consecutive same-role messages merged
        """
        if not messages:
            return messages

        merged = [messages[0].copy()]

        for message in messages[1:]:
            if message["role"] == merged[-1]["role"]:
                # Merge with previous message
                merged[-1]["content"] += "\n\n" + message["content"]
            else:
                # Add as new message
                merged.append(message.copy())

        return merged
