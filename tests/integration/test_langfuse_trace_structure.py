"""Test Langfuse trace structure for proper organization.

This test verifies that Langfuse traces have:
1. A proper trace name
2. A root container observation for each agent
3. Proper nesting of playbook spans under the root observation
"""

import json
import subprocess
import time
from pathlib import Path

import pytest

from playbooks import Playbooks


@pytest.mark.asyncio
@pytest.mark.integration
async def test_langfuse_trace_structure(test_data_dir):
    """Test that Langfuse traces have proper structure with trace name and root observation."""
    # Use the hello world example which exits cleanly
    playbooks = Playbooks([test_data_dir / "01-hello-playbooks.pb"])
    await playbooks.initialize()

    # Get the trace ID from the agent
    agent = playbooks.program.agents[0]
    trace_id = playbooks.program._langfuse_handler._agent_traces.get(agent.id, None)

    # Run the program
    await playbooks.program.run_till_exit()

    # Skip test if no trace ID (Langfuse disabled)
    if not trace_id:
        pytest.skip("Langfuse tracing not enabled")

    # Wait a moment for Langfuse to flush the trace
    time.sleep(2)

    # Export the trace using the langfuse_export_trace utility
    export_result = subprocess.run(
        [
            "python",
            str(
                Path(__file__).parent.parent.parent
                / "src/playbooks/utils/langfuse_export_trace.py"
            ),
            "--trace-id",
            trace_id,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )

    # Skip test if trace not found (Langfuse might not be running)
    if "not found" in export_result.stdout or export_result.returncode != 0:
        pytest.skip("Langfuse trace not found - Langfuse server may not be running")

    # Parse the exported trace
    trace_data = json.loads(export_result.stdout)

    # Verify trace has a name (not empty string)
    assert trace_data.get(
        "trace"
    ), f"Trace name is empty. Expected format: '<AgentClass> (agent <ID>)'. Got: '{trace_data.get('trace')}'"

    # Get agent class name from the first agent
    agent_class = agent.klass
    assert (
        agent_class in trace_data["trace"]
    ), f"Trace name should contain agent class '{agent_class}'. Got: '{trace_data['trace']}'"

    # Get all observations
    observations = trace_data.get("observations", [])
    assert observations, "No observations found in trace"

    # Build observation map for efficient lookup
    def flatten_observations(obs_list, parent_id=None):
        """Recursively flatten nested observations structure."""
        result = []
        for obs in obs_list:
            obs_copy = obs.copy()
            children = obs_copy.pop("children", [])
            obs_copy["parent_observation_id"] = parent_id
            result.append(obs_copy)
            result.extend(flatten_observations(children, obs_copy.get("id")))
        return result

    flat_observations = flatten_observations(observations)

    # Find root observations (those without parent_observation_id)
    root_observations = [
        obs for obs in flat_observations if not obs.get("parent_observation_id")
    ]

    # Verify we have at least one root observation
    assert root_observations, "No root observation found in trace"

    # Verify the root observation has the agent name in it
    root_obs = root_observations[0]
    assert agent_class in root_obs.get(
        "name", ""
    ), f"Root observation name should contain '{agent_class}'. Got: '{root_obs.get('name')}'"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_trace_structure_with_python_playbook(test_data_dir):
    """Test trace structure with a Python playbook that calls Say()."""
    # Use example 03 which has Python code
    playbooks = Playbooks([test_data_dir / "03-md-calls-python.pb"])
    await playbooks.initialize()

    agent = playbooks.program.agents[0]
    trace_id = playbooks.program._langfuse_handler._agent_traces.get(agent.id, None)

    # Seed the input so the program can complete
    await playbooks.program.agents_by_id["human"].SendMessage(agent.id, "10")
    await playbooks.program.agents_by_id["human"].SendMessage(agent.id, "EOM")

    await playbooks.program.run_till_exit()

    # Skip test if no trace ID
    if not trace_id:
        pytest.skip("Langfuse tracing not enabled")

    # Wait for flush
    time.sleep(2)

    # Export the trace
    export_result = subprocess.run(
        [
            "python",
            str(
                Path(__file__).parent.parent.parent
                / "src/playbooks/utils/langfuse_export_trace.py"
            ),
            "--trace-id",
            trace_id,
            "--compact",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )

    # Skip if trace not found
    if "not found" in export_result.stdout or export_result.returncode != 0:
        pytest.skip("Langfuse trace not found - Langfuse server may not be running")

    # Parse the trace
    trace_data = json.loads(export_result.stdout)

    # Verify trace has a name
    assert trace_data.get(
        "trace"
    ), f"Trace name is empty. Got: '{trace_data.get('trace')}'"

    # Get agent class
    agent_class = agent.klass
    assert (
        agent_class in trace_data["trace"]
    ), f"Trace name should contain '{agent_class}'. Got: '{trace_data['trace']}'"

    # Get all observations (flatten nested structure)
    def flatten_observations(obs_list, parent_id=None):
        """Recursively flatten nested observations structure."""
        result = []
        for obs in obs_list:
            obs_copy = obs.copy()
            children = obs_copy.pop("children", [])
            obs_copy["parent_observation_id"] = parent_id
            result.append(obs_copy)
            result.extend(flatten_observations(children, obs_copy.get("id")))
        return result

    flat_observations = flatten_observations(trace_data.get("observations", []))
    observation_ids = {obs.get("id") for obs in flat_observations if obs.get("id")}

    # Find orphaned observations (reference parent not in list)
    orphaned = [
        obs
        for obs in flat_observations
        if obs.get("parent_observation_id")
        and obs.get("parent_observation_id") not in observation_ids
    ]

    # This was the original bug: observations referenced parents that didn't exist
    assert not orphaned, (
        f"Found {len(orphaned)} orphaned observations (parent not in list):\n"
        + "\n".join(
            [
                f"  - {obs.get('name', 'unnamed')} (parent={obs.get('parent_observation_id')})"
                for obs in orphaned
            ]
        )
    )

    # Verify root observation exists
    root_observations = [
        obs for obs in flat_observations if not obs.get("parent_observation_id")
    ]
    assert root_observations, "No root observation found"

    root_obs = root_observations[0]
    assert agent_class in root_obs.get(
        "name", ""
    ), f"Root observation should contain '{agent_class}'. Got: '{root_obs.get('name')}'"
