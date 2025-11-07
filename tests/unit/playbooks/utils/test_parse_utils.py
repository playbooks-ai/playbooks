from playbooks.compilation.parse_utils import parse_metadata_and_description


class TestParseMetadataAndDescription:
    def test_metadata_and_description(self):
        """Test input with both metadata and description separated by ---"""
        input_text = """metadata:
  framework: GAAP
  specialization:
    - accounting
    - tax
  author: John Doe
---
This is an accountant agent that can help with accounting tasks."""

        metadata, description = parse_metadata_and_description(input_text)

        expected_metadata = {
            "framework": "GAAP",
            "specialization": ["accounting", "tax"],
            "author": "John Doe",
        }
        expected_description = (
            "This is an accountant agent that can help with accounting tasks."
        )

        assert metadata == expected_metadata
        assert description == expected_description

    def test_description_only(self):
        """Test input with only description"""
        input_text = "This is an accountant agent that can help with accounting tasks."

        metadata, description = parse_metadata_and_description(input_text)

        assert metadata == {}
        assert (
            description
            == "This is an accountant agent that can help with accounting tasks."
        )

    def test_metadata_only(self):
        """Test input with only metadata"""
        input_text = """metadata:
  framework: GAAP
  specialization:
    - accounting
    - tax
  author: John Doe"""

        metadata, description = parse_metadata_and_description(input_text)

        expected_metadata = {
            "framework": "GAAP",
            "specialization": ["accounting", "tax"],
            "author": "John Doe",
        }

        assert metadata == expected_metadata
        assert description == ""

    def test_empty_input(self):
        """Test empty input"""
        metadata, description = parse_metadata_and_description("")

        assert metadata == {}
        assert description == ""

    def test_whitespace_only_input(self):
        """Test input with only whitespace"""
        metadata, description = parse_metadata_and_description("   \n  \t  ")

        assert metadata == {}
        assert description == ""

    def test_none_input(self):
        """Test None input"""
        metadata, description = parse_metadata_and_description(None)

        assert metadata == {}
        assert description == ""

    def test_metadata_with_extra_dashes_in_description(self):
        """Test metadata and description where description contains --- delimiter"""
        input_text = """metadata:
  framework: GAAP
  author: John Doe
---
This is a description with --- some dashes in it."""

        metadata, description = parse_metadata_and_description(input_text)

        expected_metadata = {"framework": "GAAP", "author": "John Doe"}
        expected_description = "This is a description with --- some dashes in it."

        assert metadata == expected_metadata
        assert description == expected_description

    def test_complex_metadata_structure(self):
        """Test with more complex metadata structure"""
        input_text = """metadata:
  framework: GAAP
  specialization:
    - accounting
    - tax
    - audit
  author: John Doe
  version: 1.0
  tags:
    - financial
    - compliance
  config:
    max_retries: 3
    timeout: 30
---
A comprehensive accounting agent with advanced capabilities."""

        metadata, description = parse_metadata_and_description(input_text)

        expected_metadata = {
            "framework": "GAAP",
            "specialization": ["accounting", "tax", "audit"],
            "author": "John Doe",
            "version": 1.0,
            "tags": ["financial", "compliance"],
            "config": {"max_retries": 3, "timeout": 30},
        }
        expected_description = (
            "A comprehensive accounting agent with advanced capabilities."
        )

        assert metadata == expected_metadata
        assert description == expected_description
