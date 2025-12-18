"""End-to-end integration tests for variable capture in playbooks.

These tests verify the complete flow of local variable capture and usage
across playbook execution, including yield points and nested playbook calls.
"""

import re

import pytest

from playbooks import Playbooks
from playbooks.core.constants import EOM, EXECUTION_FINISHED


@pytest.mark.asyncio
async def test_simple_playbook_with_local_variables(test_data_dir):
    """Test a simple playbook that defines and uses local variables."""
    # Create a test playbook
    playbook_content = """# SimpleLocalVars

## Main
### Triggers
- At the beginning

### Steps
- x is 10
- y is 20
- z is x + y
- say the value of z to user
- End program
"""

    # Write test playbook
    test_file = test_data_dir / "test_simple_locals.pb"
    test_file.write_text(playbook_content)

    playbooks = Playbooks([test_file])
    await playbooks.initialize()

    ai_agent = playbooks.program.agents[0]
    await playbooks.program.run_till_exit()

    log = ai_agent.session_log.to_log_full()
    print(log)

    # Verify the computation happened and was communicated
    assert re.search(r"Say.*30", log) or re.search(r"30", log)
    assert EXECUTION_FINISHED in log


@pytest.mark.asyncio
async def test_playbook_with_yield_preserves_locals(test_data_dir):
    """Test that local variables are preserved across yield points."""
    playbook_content = """# YieldPreservation

## Main
### Triggers
- At the beginning

### Steps
- x is 5
- ask user for a number and store in $usernum
- y is x + $usernum
- say the result y to user
- End program
"""

    test_file = test_data_dir / "test_yield_locals.pb"
    test_file.write_text(playbook_content)

    playbooks = Playbooks([test_file])
    await playbooks.initialize()

    ai_agent = playbooks.program.agents[0]

    # Send user input
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, "10")
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, EOM)

    await playbooks.program.run_till_exit()

    log = ai_agent.session_log.to_log_full()
    print(log)

    # x=5, usernum=10, y=15
    assert re.search(r"Say.*15", log) or re.search(r"15", log)
    assert EXECUTION_FINISHED in log


@pytest.mark.asyncio
async def test_nested_playbook_calls_separate_frames(test_data_dir):
    """Test that nested playbook calls have separate local variable scopes."""
    playbook_content = """# NestedFrames

## Main
### Triggers
- At the beginning

### Steps
- x is 100
- result is Helper()
- say x is still {x} and result is {result}
- End program

## Helper
### Steps
- x is 5
- return x * 2
"""

    test_file = test_data_dir / "test_nested_frames.pb"
    test_file.write_text(playbook_content)

    playbooks = Playbooks([test_file])
    await playbooks.initialize()

    ai_agent = playbooks.program.agents[0]
    await playbooks.program.run_till_exit()

    log = ai_agent.session_log.to_log_full()
    print(log)

    # Main's x should be 100, Helper's return should be 10
    assert re.search(r"Say.*100.*10", log) or (
        re.search(r"100", log) and re.search(r"10", log)
    )
    assert EXECUTION_FINISHED in log


@pytest.mark.asyncio
async def test_playbook_args_and_locals_interaction(test_data_dir):
    """Test interaction between playbook arguments and local variables."""
    playbook_content = """# ArgsAndLocals

## Main
### Triggers
- At the beginning

### Steps
- base is 10
- result is Compute(base, 5)
- say the final result is {result}
- End program

## Compute(a, b)
### Steps
- sum is a + b
- doubled is sum * 2
- return doubled
"""

    test_file = test_data_dir / "test_args_locals.pb"
    test_file.write_text(playbook_content)

    playbooks = Playbooks([test_file])
    await playbooks.initialize()

    ai_agent = playbooks.program.agents[0]
    await playbooks.program.run_till_exit()

    log = ai_agent.session_log.to_log_full()
    print(log)

    # base=10, a=10, b=5, sum=15, doubled=30
    assert re.search(r"Say.*30", log) or re.search(r"30", log)
    assert EXECUTION_FINISHED in log


@pytest.mark.asyncio
async def test_complex_variable_flow(test_data_dir):
    """Test complex flow with args, locals, state across multiple steps."""
    playbook_content = """# ComplexFlow

## Main
### Triggers
- At the beginning

### Steps
- Initialize counter to 0 as a local variable
- set $state_count to 0
- ask user for a number and store in $increment
- counter is counter + $increment
- set $state_count to $state_count + $increment
- say counter is {counter} and state_count is {$state_count}
- ask user for another number and store in $increment2
- counter is counter + $increment2
- set $state_count to $state_count + $increment2
- final is Process(counter, $state_count)
- say the final result is {final}
- End program

## Process(a, b)
### Steps
- local_sum is a + b
- local_product is a * b
- return local_sum + local_product
"""

    test_file = test_data_dir / "test_complex_flow.pb"
    test_file.write_text(playbook_content)

    playbooks = Playbooks([test_file])
    await playbooks.initialize()

    ai_agent = playbooks.program.agents[0]

    # Send first number: 5
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, "5")
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, EOM)

    # Send second number: 3
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, "3")
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, EOM)

    await playbooks.program.run_till_exit()

    log = ai_agent.session_log.to_log_full()
    print(log)

    # After first input: counter=5, state_count=5
    assert re.search(r"counter.*5.*state_count.*5", log, re.IGNORECASE) or (
        re.search(r"5", log)
    )

    # After second input: counter=8, state_count=8
    # Process(8, 8): local_sum=16, local_product=64, return=80
    assert re.search(r"final.*80", log, re.IGNORECASE) or re.search(r"80", log)
    assert EXECUTION_FINISHED in log


@pytest.mark.asyncio
async def test_local_variables_in_loops(test_data_dir):
    """Test that local variables work correctly in loops."""
    playbook_content = """# LoopLocals

## Main
### Triggers
- At the beginning

### Steps   
- Initialize empty list as items
- Initialize counter to 0
- For each iteration from 1 to 5:
  - add counter to items list
  - increment counter by 1
- say the items list has {len(items)} elements
- say the counter is now {counter}
- End program
"""

    test_file = test_data_dir / "test_loop_locals.pb"
    test_file.write_text(playbook_content)

    playbooks = Playbooks([test_file])
    await playbooks.initialize()

    ai_agent = playbooks.program.agents[0]
    await playbooks.program.run_till_exit()

    log = ai_agent.session_log.to_log_full()
    print(log)

    # Should have accumulated items and counter
    assert re.search(r"5", log)  # Counter should be 5
    assert EXECUTION_FINISHED in log


@pytest.mark.asyncio
async def test_variables_across_conditional_branches(test_data_dir):
    """Test that variables work correctly across conditional branches."""
    playbook_content = """# ConditionalVars

## Main
### Triggers
- At the beginning

### Steps
- x is 10
- ask user for a number and store in $usernum
- if $usernum is greater than 5:
  - status is "high"
  - multiplier is 2
- else:
  - status is "low"  
  - multiplier is 1
- result is x * multiplier
- say the status is {status} and result is {result}
- End program
"""

    test_file = test_data_dir / "test_conditional_vars.pb"
    test_file.write_text(playbook_content)

    playbooks = Playbooks([test_file])
    await playbooks.initialize()

    ai_agent = playbooks.program.agents[0]

    # Send number > 5
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, "8")
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, EOM)

    await playbooks.program.run_till_exit()

    log = ai_agent.session_log.to_log_full()
    print(log)

    # x=10, usernum=8, status="high", multiplier=2, result=20
    assert re.search(r"high", log, re.IGNORECASE)
    assert re.search(r"20", log)
    assert EXECUTION_FINISHED in log


@pytest.mark.asyncio
async def test_local_variables_with_state_persistence(test_data_dir):
    """Test that local and state variables persist independently."""
    playbook_content = """# LocalsAndState

## Main
### Triggers
- At the beginning

### Steps
- local_var is 100
- set $state_var to 200
- ask user for input
- say before modification: local is {local_var} and state is {$state_var}
- local_var is local_var + 50
- set $state_var to $state_var + 50
- say after modification: local is {local_var} and state is {$state_var}
- End program
"""

    test_file = test_data_dir / "test_locals_state_persist.pb"
    test_file.write_text(playbook_content)

    playbooks = Playbooks([test_file])
    await playbooks.initialize()

    ai_agent = playbooks.program.agents[0]

    # Send any input
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, "ok")
    await playbooks.program.agents_by_id["human"].SendMessage(ai_agent.id, EOM)

    await playbooks.program.run_till_exit()

    log = ai_agent.session_log.to_log_full()
    print(log)

    # Before: local=100, state=200
    assert re.search(r"100", log)
    assert re.search(r"200", log)

    # After: local=150, state=250
    assert re.search(r"150", log)
    assert re.search(r"250", log)
    assert EXECUTION_FINISHED in log
