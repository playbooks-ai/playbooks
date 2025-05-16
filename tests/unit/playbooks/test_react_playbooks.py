from pathlib import Path

from playbooks.playbook import Playbook
from playbooks.enums import PlaybookExecutionType
from playbooks.utils.markdown_to_ast import markdown_to_ast


def test_react_playbook_detection():
    """Test that a playbook without Steps section is detected as a ReAct playbook."""
    test_file_path = (
        Path(__file__).parent.parent.parent
        / "data"
        / "react"
        / "basic_react_playbook.md"
    )

    with open(test_file_path, "r") as f:
        markdown_content = f.read()

    ast = markdown_to_ast(markdown_content)

    h1_node = None
    for node in ast.get("children", []):
        if node.get("type") == "h1" and node.get("text", "") == "TestAgent":
            h1_node = node
            break

    assert h1_node is not None, "Could not find TestAgent H1 node in AST"

    h2_node = None
    for node in h1_node.get("children", []):
        if node.get("type") == "h2" and node.get("text", "") == "SimpleReact":
            h2_node = node
            break

    assert h2_node is not None, "Could not find SimpleReact H2 node in AST"

    playbook = Playbook.from_h2(h2_node)

    assert playbook.execution_type == PlaybookExecutionType.REACT

    assert playbook.description is not None
    assert "<output_format>" in playbook.description
    assert "<style_guide>" in playbook.description

    assert playbook.step_collection is not None
    assert len(playbook.step_collection.steps) > 0

    steps = playbook.step_collection.steps
    for step_id, step in steps.items():
        print(f"Step {step_id}: {step.content}")

    assert any("Think deeply about the task" in step.content for step in steps.values())
    assert any("Initialize $task_status" in step.content for step in steps.values())
    assert any("While $task_status is not" in step.content for step in steps.values())
