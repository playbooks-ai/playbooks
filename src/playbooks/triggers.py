"""Playbook trigger system for reactive execution.

This module provides the trigger system that allows playbooks to be started
based on various conditions and events, enabling reactive agent behavior.
"""

from typing import List, Optional


class PlaybookTrigger:
    """Represents a trigger that can start a playbook."""

    def __init__(
        self,
        playbook_klass: str,
        playbook_signature: str,
        trigger: str,
        source_line_number: Optional[int] = None,
    ):
        """Initialize a PlaybookTrigger.

        Args:
            playbook_klass: The class name of the playbook.
            playbook_signature: The signature of the playbook function.
            trigger: The trigger string.
            source_line_number: The line number in the source markdown where this
                trigger is defined.
        """
        self.playbook_klass = playbook_klass
        self.playbook_signature = playbook_signature
        self.trigger = trigger
        self.source_line_number = source_line_number
        # Example text: "01:BGN When the agent starts running"
        self.trigger_name = self.trigger.split(" ")[0]
        self.trigger_description = " ".join(self.trigger.split(" ")[1:])
        self.is_begin = "BGN" in self.trigger_name

    def __str__(self) -> str:
        """Return a string representation of the trigger."""
        return self.trigger_instruction()

    def trigger_instruction(self, namespace: Optional[str] = None) -> str:
        if not namespace:
            namespace = ""
        else:
            namespace = namespace + "."

        signature = namespace + self.playbook_signature.split(" ->")[0]
        return f'- {self.trigger_description}, `Trigger["{namespace}{self.playbook_klass}:{self.trigger_name}"]` by enqueuing `{signature}`'


class PlaybookTriggers:
    """Collection of triggers for a playbook."""

    def __init__(
        self,
        playbook_klass: str,
        playbook_signature: str,
        triggers: List[str],
        trigger_line_numbers: Optional[List[Optional[int]]] = None,
        source_line_number: Optional[int] = None,
    ):
        """Initialize a PlaybookTriggers collection.

        Args:
            playbook_klass: The class name of the playbook.
            playbook_signature: The signature of the playbook function.
            triggers: List of trigger strings.
            trigger_line_numbers: List of line numbers for each trigger.
            source_line_number: The line number in the source markdown where this
                triggers section is defined.
        """
        self.playbook_klass = playbook_klass
        self.playbook_signature = playbook_signature
        self.source_line_number = source_line_number

        if trigger_line_numbers is None:
            trigger_line_numbers = [None] * len(triggers)

        self.triggers = [
            PlaybookTrigger(
                playbook_klass=self.playbook_klass,
                playbook_signature=self.playbook_signature,
                trigger=trigger,
                source_line_number=line_num,
            )
            for trigger, line_num in zip(triggers, trigger_line_numbers)
        ]
