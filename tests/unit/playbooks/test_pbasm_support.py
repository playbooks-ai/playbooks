#!/usr/bin/env python
"""
Test script to verify .pbasm file support in the playbooks framework.
"""

# Add the src directory to the Python path
import pytest

from playbooks import Playbooks
from playbooks.utils.file_utils import (
    get_file_type_description,
    has_compiled_playbook_files,
    is_compiled_playbook_file,
    is_playbook_file,
    is_source_playbook_file,
)


def test_file_utils():
    """Test the file utility functions."""
    print("Testing file utility functions...")

    # Test compiled file detection
    assert is_compiled_playbook_file("test.pbasm")
    assert not is_compiled_playbook_file("test.pb")
    assert not is_compiled_playbook_file("test.playbooks")
    assert not is_compiled_playbook_file("test.txt")
    print("✓ Compiled file detection works")

    # Test source file detection
    assert is_source_playbook_file("test.pb")
    assert is_source_playbook_file("test.playbooks")
    assert not is_source_playbook_file("test.pbasm")
    assert not is_source_playbook_file("test.txt")
    print("✓ Source file detection works")

    # Test general playbook file detection
    assert is_playbook_file("test.pb")
    assert is_playbook_file("test.pbasm")
    assert is_playbook_file("test.playbooks")
    assert not is_playbook_file("test.txt")
    print("✓ General playbook file detection works")

    # Test compiled files in list
    assert has_compiled_playbook_files(["test.pb", "test.pbasm"])
    assert not has_compiled_playbook_files(["test.pb", "test.playbooks"])
    assert has_compiled_playbook_files(["test.pbasm"])
    assert not has_compiled_playbook_files(["test.pb"])
    print("✓ Compiled files in list detection works")

    # Test file type descriptions
    assert get_file_type_description("test.pbasm") == "compiled playbook"
    assert get_file_type_description("test.pb") == "source playbook"
    assert get_file_type_description("test.playbooks") == "source playbook"
    assert get_file_type_description("test.txt") == "unknown file type"
    print("✓ File type descriptions work")


@pytest.mark.asyncio
async def test_playbooks_compilation_skip(test_data_dir):
    """Test that Playbooks class skips compilation for .pbasm files."""
    print("\nTesting Playbooks compilation skip...")

    pb_file_path = test_data_dir / "02-personalized-greeting.pb"
    pbasm_file_path = test_data_dir / "02-personalized-greeting.pbasm"

    source_content = pb_file_path.read_text()
    compiled_content = pbasm_file_path.read_text()

    # Test with .pbasm file - should skip compilation
    print(f"Testing with .pbasm file: {pbasm_file_path}")
    playbooks_pbasm = Playbooks([pbasm_file_path])

    # The compiled content should be the same as the original content
    assert playbooks_pbasm.compiled_program_content == compiled_content
    print("✓ .pbasm file compilation skipped correctly")

    # Test with .pb file - should compile (but we'll just check it's different)
    print(f"Testing with .pb file: {pb_file_path}")
    playbooks_pb = Playbooks([pb_file_path])

    # The compiled content should be different from the original content
    # (because compilation adds processing steps)
    assert playbooks_pb.compiled_program_content != source_content
    print("✓ .pb file compilation executed correctly")
