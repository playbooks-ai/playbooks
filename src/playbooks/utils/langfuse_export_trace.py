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

    # Sort all observations by startTime (or createdAt as fallback) chronologically (oldest first)
    def get_sort_key(obs):
        # Primary: use startTime for actual chronological order
        # Fallback: use createdAt if startTime not available
        timestamp = (
            obs.get("start_time")
            or obs.get("startTime")
            or obs.get("created_at")
            or obs.get("createdAt")
        )

        if timestamp is None:
            timestamp_dt = datetime.min
        elif isinstance(timestamp, datetime):
            timestamp_dt = timestamp
        elif isinstance(timestamp, str):
            try:
                timestamp_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                timestamp_dt = datetime.min
        else:
            timestamp_dt = datetime.min

        # Secondary sort by id to ensure stable ordering when timestamps are identical
        obs_id = obs.get("id", "")

        return (timestamp_dt, obs_id)

    obs_list.sort(key=get_sort_key)

    observation_map = {obs["id"]: obs for obs in obs_list}
    for obs in obs_list:
        # Support both snake_case (v3 API) and camelCase (v2 API)
        parent_id = obs.get("parent_observation_id") or obs.get("parentObservationId")
        if parent_id and parent_id in observation_map:
            parent = observation_map[parent_id]
            if "children" not in parent:
                parent["children"] = []
            parent["children"].append(obs)

    # Return root observations (those without a parent in the observation set)
    # Support both snake_case and camelCase
    root_obs = [
        obs
        for obs in obs_list
        if not (obs.get("parent_observation_id") or obs.get("parentObservationId"))
        or (
            (obs.get("parent_observation_id") or obs.get("parentObservationId"))
            not in observation_map
        )
    ]
    return root_obs


def filter_keys(obj: Any, keys_to_keep: Optional[set] = None) -> Any:
    """Recursively filter to keep only specified keys from nested dictionaries and lists.

    This function traverses the entire data structure and at each dictionary level,
    only keeps the keys that are in the keys_to_keep set. Special keys like
    'observations' and 'children' are always preserved to maintain the hierarchy.

    Args:
        obj: Object to filter (dict, list, or primitive)
        keys_to_keep: Set of keys to keep, if None returns object as-is

    Returns:
        Filtered object with only specified keys retained
    """
    if keys_to_keep is None:
        return obj

    # Always preserve hierarchical structure keys
    structural_keys = {"observations", "children"}

    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            # Keep structural keys to maintain hierarchy
            if k in structural_keys:
                result[k] = filter_keys(v, keys_to_keep)
            # Keep requested keys
            elif k in keys_to_keep:
                result[k] = filter_keys(v, keys_to_keep)
        return result
    elif isinstance(obj, list):
        return [filter_keys(item, keys_to_keep) for item in obj]
    else:
        return obj


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
            "createdAt",
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
            "unit",
            "totalTokens",
            "completionTokens",
            "projectId",
            "usagePricingTierId",
            "usagePricingTierName",
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
    trace_id: str,
    save_to_file: bool = False,
    for_diff: bool = False,
    keys_to_keep: Optional[set] = None,
) -> None:
    try:
        # Fetch the trace and its observations using v3 API
        trace_response = langfuse.api.trace.get(trace_id)

        # Fetch all observations with proper pagination and ordering
        all_observations = []
        page = 1
        page_size = 100

        while True:
            observations_response = langfuse.api.observations.get_many(
                trace_id=trace_id, page=page, limit=page_size
            )

            # Extract observations from the response object
            # In v3 API, get_many returns a response with 'data' attribute
            page_observations = (
                observations_response.data
                if hasattr(observations_response, "data")
                else observations_response
            )

            # Convert ObservationsView to list if needed
            if not isinstance(page_observations, list):
                page_observations = list(page_observations)

            if not page_observations:
                break

            all_observations.extend(page_observations)

            # Check if there are more pages
            if len(page_observations) < page_size:
                break

            page += 1

        observations = all_observations

        # Convert trace response to dictionary
        if hasattr(trace_response, "model_dump"):
            trace_dict = trace_response.model_dump(mode="python")
        elif hasattr(trace_response, "__dict__"):
            trace_dict = vars(trace_response)
        else:
            trace_dict = trace_response

        # Structure the observations hierarchically
        structured_observations = get_nested_observations(observations)

        # Create the JSON export object
        export_data = {
            "trace": trace_dict.get("name", trace_id),
            "observations": structured_observations,
        }

        # Filter to specific keys if requested
        if keys_to_keep:
            export_data = filter_keys(export_data, keys_to_keep)

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
    parser.add_argument(
        "--keys",
        type=str,
        help="Comma-separated list of keys to output (e.g., 'trace,name,observations')",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Shortcut for --keys 'trace,observations,name'",
    )

    args = parser.parse_args()

    # Handle --compact as a shortcut for specific keys
    keys_to_keep = None
    if args.compact:
        keys_to_keep = {"trace", "observations", "name"}
    elif args.keys:
        # Parse comma-separated keys and strip whitespace
        keys_to_keep = {key.strip() for key in args.keys.split(",")}

    export_observations(args.trace_id, args.save_to_file, args.for_diff, keys_to_keep)


# Example usage:
# Basic export:
#   poetry run python src/playbooks/utils/langfuse_export_trace.py --trace-id <trace_id>
#
# Save to file:
#   poetry run python src/playbooks/utils/langfuse_export_trace.py --save-to-file --trace-id <trace_id>
#
# Compact output (trace, observations, name only):
#   poetry run python src/playbooks/utils/langfuse_export_trace.py --compact --trace-id <trace_id>
#
# Custom keys:
#   poetry run python src/playbooks/utils/langfuse_export_trace.py --keys "name,type,model" --trace-id <trace_id>
#
# Diff two traces:
#   code --diff $(poetry run python src/playbooks/utils/langfuse_export_trace.py --save-to-file --for-diff --trace-id <trace_id_1>) $(poetry run python src/playbooks/utils/langfuse_export_trace.py --save-to-file --for-diff --trace-id <trace_id_2>)
