"""
Test script to verify that importlib.resources.files works with playbooks.examples.
"""

import importlib.resources


def list_examples():
    """List all examples in the playbooks.examples package."""
    examples_path = importlib.resources.files("playbooks.examples")
    print(f"Examples path: {examples_path}")

    # List all files in the examples directory
    print("\nPlaybooks examples:")
    playbooks_path = examples_path / "playbooks"
    if playbooks_path.exists():
        for file in playbooks_path.glob("*.md"):
            print(f"- {file.name}")

    print("\nLanggraph examples:")
    langgraph_path = examples_path / "langgraph"
    if langgraph_path.exists():
        for file in langgraph_path.glob("*.py"):
            print(f"- {file.name}")


if __name__ == "__main__":
    list_examples()
