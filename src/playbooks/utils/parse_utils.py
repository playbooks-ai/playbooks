"""
Example input with both config and description --
config:
  framework: GAAP
  specialization:
    - accounting
    - tax
  author: John Doe
---
This is an accountant agent that can help with accounting tasks.

Example input with only description --
This is an accountant agent that can help with accounting tasks.

Example input with only config --
config:
  framework: GAAP
  specialization:
    - accounting
    - tax
  author: John Doe

Also, input can be empty.
"""

import re

import yaml


def parse_config_and_description(input: str) -> tuple[dict, str]:
    """Parse the input into a config and description."""
    if not input or not input.strip():
        return {}, ""

    # Check if there's a config section
    config_match = re.search(
        r"^config:\s*\n(.*?)(?=\n\S|\Z)", input, re.MULTILINE | re.DOTALL
    )

    config = {}
    description = ""

    if config_match:
        # Extract and parse the config section
        config_content = config_match.group(1)
        try:
            config = yaml.safe_load(config_content) or {}
        except yaml.YAMLError:
            config = {}

        # Remove the config section from input to get description
        config_section = config_match.group(0)
        remaining_text = input.replace(config_section, "", 1).strip()
        description = remaining_text
    else:
        # No config section found, treat entire input as description
        description = input.strip()

    return config, description
