"""Variable management system for playbook execution.

Uses DotMap for attribute-style access (state.x) with diff-based change tracking.
"""

import types
from typing import Any, Dict, Optional

from dotmap import DotMap

from playbooks.core.events import VariableUpdateEvent
from playbooks.infrastructure.event_bus import EventBus


class PlaybookDotMap(DotMap):
    """Custom DotMap that supports format specifiers in f-strings.

    This subclass fixes the issue where DotMap objects don't support format
    specifiers like `:,` in f-strings. When accessing dictionary values via
    __getitem__, primitive types (int, str, float, bool, None) are returned
    as native Python types to support format specifiers.

    When format specifiers are used on a DotMap itself, it converts to a
    native dict for formatting.
    """

    def __format__(self, format_spec: str) -> str:
        """Format DotMap with format specifiers by converting to dict first.

        Args:
            format_spec: Format specification (e.g., ':,' for number formatting)

        Returns:
            Formatted string representation
        """
        # Convert to native dict to support format specifiers
        native_dict = self._to_native_dict(self)
        # Format the dict using the format spec
        if format_spec:
            return format(native_dict, format_spec)
        return str(native_dict)

    def __getitem__(self, key: Any) -> Any:
        """Get item, returning native types for primitives.

        This ensures that when accessing nested dictionary values like
        report_data['sales'], we get a native int that supports format
        specifiers, rather than a DotMap-wrapped value.

        Args:
            key: Dictionary key

        Returns:
            Native Python type for primitives, PlaybookDotMap for dicts
        """
        value = super().__getitem__(key)
        # If it's a dict-like DotMap, keep it as PlaybookDotMap for nested access
        if isinstance(value, DotMap) and not isinstance(value, PlaybookDotMap):
            # Convert to PlaybookDotMap for consistency
            return PlaybookDotMap(value)
        # For primitive values, ensure they're native types
        # DotMap should already return primitives as-is, but be safe
        if isinstance(value, (int, str, float, bool, type(None))):
            return value
        # For dicts stored in DotMap, they become DotMap - keep as PlaybookDotMap
        if isinstance(value, dict):
            return PlaybookDotMap(value)
        return value

    @staticmethod
    def _to_native_dict(value: Any) -> Any:
        """Recursively convert DotMap to native dict.

        Args:
            value: Value to convert

        Returns:
            Native Python dict/list/primitive
        """
        if isinstance(value, (DotMap, dict)):
            result = {}
            for k, v in dict(value).items():
                result[k] = PlaybookDotMap._to_native_dict(v)
            return result
        elif isinstance(value, list):
            return [PlaybookDotMap._to_native_dict(item) for item in value]
        else:
            return value


class Artifact:
    """Artifact with summary and value for large content.

    Artifacts are used for values that exceed the artifact_result_threshold,
    allowing the LLM to see a summary without the full content in every message.
    """

    def __init__(self, name: str, summary: str, value: Any):
        """Initialize an Artifact.

        Args:
            name: Artifact name
            summary: Short summary of the artifact
            value: The actual content/value
        """
        self.name = name
        self.summary = summary
        self.value = value

    def __repr__(self) -> str:
        return f"Artifact({self.name}: {self.summary})"

    def __str__(self) -> str:
        return str(self.value)

    # String operations - delegate to value
    def __len__(self) -> int:
        return len(str(self.value))

    def __add__(self, other):
        return str(self.value) + str(other)

    def __radd__(self, other):
        return str(other) + str(self.value)

    def __mul__(self, n):
        return str(self.value) * n

    def __rmul__(self, n):
        return n * str(self.value)

    def __getitem__(self, key) -> str:
        return str(self.value)[key]

    def __contains__(self, item: Any) -> bool:
        return str(item) in str(self.value)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Artifact):
            return self.value == other.value
        return str(self.value) == str(other)

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Artifact):
            return str(self.value) < str(other.value)
        return str(self.value) < str(other)

    def __le__(self, other: Any) -> bool:
        if isinstance(other, Artifact):
            return str(self.value) <= str(other.value)
        return str(self.value) <= str(other)

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, Artifact):
            return str(self.value) > str(other.value)
        return str(self.value) > str(other)

    def __ge__(self, other: Any) -> bool:
        if isinstance(other, Artifact):
            return str(self.value) >= str(other.value)
        return str(self.value) >= str(other)


class VariablesTracker:
    """Static utility methods for computing variable diffs and publishing events."""

    @staticmethod
    def snapshot(variables: DotMap) -> Dict[str, Any]:
        """Create a snapshot of variables for diff computation.

        Args:
            variables: DotMap to snapshot

        Returns:
            Dictionary copy of variables
        """
        return dict(variables)

    @staticmethod
    def compute_diff(
        current: DotMap, previous: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute diff between current and previous state.

        Args:
            current: Current variables DotMap
            previous: Previous snapshot (or None for full state)

        Returns:
            Dict with new_variables, changed_variables, deleted_variables
        """
        if previous is None:
            # No previous state - return everything as new
            return {"variables": VariablesTracker.to_dict(current)}

        diff = {}
        current_dict = dict(current)

        # Find new and changed variables
        new_vars = {}
        changed_vars = {}
        for key, value in current_dict.items():
            if key.startswith("_"):
                continue
            if key not in previous:
                new_vars[key] = VariablesTracker._format_value(value)
            elif previous[key] != value:
                changed_vars[key] = VariablesTracker._format_value(value)

        # Find deleted variables
        deleted_vars = [
            key
            for key in previous
            if not key.startswith("_") and key not in current_dict
        ]

        if new_vars:
            diff["new_variables"] = new_vars
        if changed_vars:
            diff["changed_variables"] = changed_vars
        if deleted_vars:
            diff["deleted_variables"] = deleted_vars

        return diff

    @staticmethod
    def publish_changes(
        event_bus: EventBus,
        agent_id: str,
        current: DotMap,
        previous: Optional[Dict[str, Any]],
    ) -> None:
        """Publish VariableUpdateEvent for all changes.

        Args:
            event_bus: Event bus to publish to
            agent_id: Agent ID
            current: Current variables
            previous: Previous snapshot
        """
        if not event_bus or previous is None:
            return

        diff = VariablesTracker.compute_diff(current, previous)

        # Publish event for each new/changed variable
        for key in diff.get("new_variables", {}):
            event = VariableUpdateEvent(
                agent_id=agent_id,
                session_id="",
                variable_name=key,
                variable_value=current[key],
            )
            event_bus.publish(event)

        for key in diff.get("changed_variables", {}):
            event = VariableUpdateEvent(
                agent_id=agent_id,
                session_id="",
                variable_name=key,
                variable_value=current[key],
            )
            event_bus.publish(event)

    @staticmethod
    def to_dict(variables: DotMap, include_private: bool = False) -> Dict[str, Any]:
        """Convert variables to dictionary for state output.

        Args:
            variables: DotMap to convert
            include_private: Include private variables starting with _

        Returns:
            Dictionary representation
        """
        result = {}
        for key, value in dict(variables).items():
            if key.startswith("_") and not include_private:
                continue
            if value is None:
                continue
            if isinstance(value, (types.ModuleType, type)):
                continue

            result[key] = VariablesTracker._format_value(value)

        return result

    @staticmethod
    def public_variables(variables: DotMap) -> Dict[str, Any]:
        """Get public variables only.

        Args:
            variables: DotMap to filter

        Returns:
            Dictionary of public variables (excludes None values and private vars)
        """
        return {
            key: value
            for key, value in dict(variables).items()
            if not key.startswith("_") and value is not None
        }

    @staticmethod
    def _format_value(value: Any) -> Any:
        """Format a value for state output."""
        if isinstance(value, Artifact):
            return f"Artifact: {value.summary}"
        return value


# Backwards compatibility alias - use PlaybookDotMap instead of DotMap
Variables = PlaybookDotMap
