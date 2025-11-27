"""Langfuse trace export utilities.

This module provides functionality to export traces and observations from
Langfuse for debugging and analysis purposes.
"""

import argparse
import json
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional

import dotenv
from langfuse import get_client

dotenv.load_dotenv()


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects and other non-serializable types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return "[redacted]"
        # Handle Pydantic models
        if hasattr(obj, "model_dump"):
            return obj.model_dump(mode="python")
        # Handle objects with __dict__
        if hasattr(obj, "__dict__"):
            return vars(obj)
        # Fallback to string representation
        return str(obj)


# Initialize Langfuse client using v3 API
langfuse = get_client()
if not langfuse:
    raise ValueError(
        "Failed to initialize Langfuse client. Check your environment variables in .env file. "
        "LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, and LANGFUSE_HOST must be set."
    )


def get_nested_observations(observations: List[Any]) -> List[Dict[str, Any]]:
    """Organize observations hierarchically, maintaining chronological order.

    Args:
        observations: List of observation objects or dictionaries

    Returns:
        Root observations with children nested hierarchically
    """
    # Convert observations to dictionaries if they're objects
    obs_list = []
    for obs in observations:
        if hasattr(obs, "__dict__"):
            # If it's an object, convert to dict
            obs_dict = (
                obs.model_dump(mode="python")
                if hasattr(obs, "model_dump")
                else vars(obs)
            )
        else:
            # If it's already a dict, use as-is
            obs_dict = obs
        obs_list.append(obs_dict)

    # Sort all observations by createdAt chronologically
    obs_list.sort(key=lambda x: x.get("createdAt") or "")

    observation_map = {obs["id"]: obs for obs in obs_list}
    for obs in obs_list:
        parent_id = obs.get("parentObservationId")
        if parent_id and parent_id in observation_map:
            parent = observation_map[parent_id]
            if "children" not in parent:
                parent["children"] = []
            parent["children"].append(obs)

    # Return root observations, sorted chronologically
    root_obs = [obs for obs in obs_list if not obs.get("parentObservationId")]
    return root_obs


def remove_keys_for_diff(obj: Any, keys_to_remove: Optional[set] = None) -> Any:
    """Recursively remove specified keys from nested dictionaries and lists.

    Args:
        obj: Object to clean (dict, list, or primitive)
        keys_to_remove: Set of keys to remove, uses default if None

    Returns:
        Cleaned object with specified keys removed
    """
    if keys_to_remove is None:
        keys_to_remove = {
            # "createdAt",
            "id",
            "calculated_input_cost",
            "calculated_output_cost",
            "calculated_total_cost",
            "cost_details",
            "latency",
            # "cache_hit",
            "parent_observation_id",
            "trace_id",
            "updatedAt",
        }

    if isinstance(obj, dict):
        return {
            k: remove_keys_for_diff(v, keys_to_remove)
            for k, v in obj.items()
            if k not in keys_to_remove
        }
    elif isinstance(obj, list):
        return [remove_keys_for_diff(item, keys_to_remove) for item in obj]
    else:
        return obj


def export_observations(
    trace_id: str, save_to_file: bool = False, for_diff: bool = False
) -> None:
    try:
        # Fetch the trace and its observations
        trace_response = langfuse.fetch_trace(trace_id)
        observations_response = langfuse.fetch_observations(trace_id=trace_id)

        # Convert trace response to dictionary
        if hasattr(trace_response, "model_dump"):
            trace_dict = trace_response.model_dump(mode="python")
        elif hasattr(trace_response, "__dict__"):
            trace_dict = vars(trace_response)
        else:
            trace_dict = trace_response

        # Extract observations from the response object
        observations = (
            observations_response.observations
            if hasattr(observations_response, "observations")
            else observations_response.data
        )

        # Convert ObservationsView to list if needed
        if not isinstance(observations, list):
            observations = list(observations)

        # Structure the observations hierarchically
        structured_observations = get_nested_observations(observations)

        # Create the JSON export object
        export_data = {
            "trace": trace_dict.get("name", trace_id),
            "observations": structured_observations,
        }

        # Remove keys for diff if requested
        if for_diff:
            export_data = remove_keys_for_diff(export_data)

        # Convert to JSON (without sort_keys to preserve chronological order)
        json_export = json.dumps(
            export_data, indent=2, sort_keys=False, cls=DateTimeEncoder
        )

        # Output the JSON (or save to a file)
        if save_to_file:
            # Use temp file
            fd, path = tempfile.mkstemp(
                prefix="langfuse_trace_", suffix=".json", dir=tempfile.gettempdir()
            )
            with open(fd, "w") as f:
                f.write(json_export)
                f.flush()
                # Print full file path
            print(path)
        else:
            print(json_export)

    except Exception as e:
        print("Error exporting observations:", e)


# Example usage
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-id", type=str, required=True)
    parser.add_argument("--save-to-file", action="store_true")
    parser.add_argument("--for-diff", action="store_true")

    args = parser.parse_args()
    export_observations(args.trace_id, args.save_to_file, args.for_diff)


# Example usage
# poetry run python src/playbooks/utils/langfuse_export_trace.py --save-to-file --trace-id <trace_id>

# Diff two traces
# code --diff $(poetry run python src/playbooks/utils/langfuse_export_trace.py  --save-to-file --for-diff --trace-id <trace_id_1>) $(poetry run python src/playbooks/utils/langfuse_export_trace.py --save-to-file --for-diff--trace-id <trace_id_2>)
