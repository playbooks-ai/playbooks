#!/usr/bin/env python
"""
Test script to verify .pbasm file support in the playbooks framework.
"""

# Add the src directory to the Python path
from pathlib import Path

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
async def test_playbooks_compilation_skip(test_data_dir, tmp_path):
    """Test that Playbooks class skips compilation for .pbasm files."""
    # Use an existing .pb file from test data
    pb_file_path = test_data_dir / "02-personalized-greeting.pb"
    source_content = pb_file_path.read_text()

    # First, compile the .pb file to get the compiled content
    playbooks_pb = Playbooks([str(pb_file_path)])
    pbasm_file_path = playbooks_pb.compiled_program_files[0].compiled_file_path

    # The compiled content should be different from the original content
    # (because compilation adds processing steps)
    pbasm_file_path = Path(pbasm_file_path).absolute()
    assert pbasm_file_path.read_text() != source_content

    # Test with .pbasm file - should skip compilation
    playbooks_pbasm = Playbooks([str(pbasm_file_path)])

    # The compiled content should be the same as what we wrote to the .pbasm file
    # (no additional compilation should occur)
    assert str(playbooks_pbasm.compiled_program_files[0].file_path) == str(
        pbasm_file_path
    )
    assert str(playbooks_pbasm.compiled_program_files[0].compiled_file_path) == str(
        pbasm_file_path
    )
