from playbooks.utils.parse_utils import parse_config_and_description


class TestParseConfigAndDescription:
    def test_both_config_and_description(self):
        """Test input with both config and description."""
        input_text = """config:
  framework: GAAP
  specialization:
    - accounting
    - tax
  author: John Doe
This is an accountant agent that can help with accounting tasks."""

        config, description = parse_config_and_description(input_text)

        expected_config = {
            "framework": "GAAP",
            "specialization": ["accounting", "tax"],
            "author": "John Doe",
        }
        expected_description = (
            "This is an accountant agent that can help with accounting tasks."
        )

        assert config == expected_config
        assert description == expected_description

    def test_only_description(self):
        """Test input with only description."""
        input_text = "This is an accountant agent that can help with accounting tasks."

        config, description = parse_config_and_description(input_text)

        assert config == {}
        assert (
            description
            == "This is an accountant agent that can help with accounting tasks."
        )

    def test_only_config(self):
        """Test input with only config."""
        input_text = """config:
  framework: GAAP
  specialization:
    - accounting
    - tax
  author: John Doe"""

        config, description = parse_config_and_description(input_text)

        expected_config = {
            "framework": "GAAP",
            "specialization": ["accounting", "tax"],
            "author": "John Doe",
        }

        assert config == expected_config
        assert description == ""

    def test_empty_input(self):
        """Test empty input."""
        config, description = parse_config_and_description("")

        assert config == {}
        assert description == ""

    def test_whitespace_only_input(self):
        """Test input with only whitespace."""
        config, description = parse_config_and_description("   \n\t  ")

        assert config == {}
        assert description == ""

    def test_config_with_multiline_description(self):
        """Test config with multiline description."""
        input_text = """config:
  framework: GAAP
  author: John Doe
This is an accountant agent that can help with accounting tasks.
It supports various accounting frameworks and specializations.
Perfect for financial reporting and tax preparation."""

        config, description = parse_config_and_description(input_text)

        expected_config = {"framework": "GAAP", "author": "John Doe"}
        expected_description = """This is an accountant agent that can help with accounting tasks.
It supports various accounting frameworks and specializations.
Perfect for financial reporting and tax preparation."""

        assert config == expected_config
        assert description == expected_description

    def test_invalid_yaml_config(self):
        """Test handling of invalid YAML in config section."""
        input_text = """config:
  framework: GAAP
  invalid: [unclosed bracket
  author: John Doe
This is a description."""

        config, description = parse_config_and_description(input_text)

        # Should handle invalid YAML gracefully
        assert config == {}
        assert description == "This is a description."

    def test_simple_config(self):
        """Test simple config with basic key-value pairs."""
        input_text = """config:
  name: Test Agent
  version: 1.0
Simple test agent description."""

        config, description = parse_config_and_description(input_text)

        expected_config = {"name": "Test Agent", "version": 1.0}

        assert config == expected_config
        assert description == "Simple test agent description."

    def test_config_with_nested_objects(self):
        """Test config with nested objects."""
        input_text = """config:
  metadata:
    name: Complex Agent
    version: 2.0
    settings:
      debug: true
      timeout: 30
Agent with complex configuration structure."""

        config, description = parse_config_and_description(input_text)

        expected_config = {
            "metadata": {
                "name": "Complex Agent",
                "version": 2.0,
                "settings": {"debug": True, "timeout": 30},
            }
        }

        assert config == expected_config
        assert description == "Agent with complex configuration structure."

    def test_description_only_multiline(self):
        """Test multiline description without config."""
        input_text = """This is a multiline description
that spans multiple lines
and contains various information."""

        config, description = parse_config_and_description(input_text)

        assert config == {}
        assert description == input_text
