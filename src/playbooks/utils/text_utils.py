"""Text processing utilities.

This module provides various text manipulation functions used throughout
the playbooks framework for string processing and formatting.
"""


def simple_shorten(text: str, width: int, placeholder: str = "...") -> str:
    """Shorten text to fit within specified width.

    Args:
        text: Text to shorten
        width: Maximum width (including placeholder)
        placeholder: String to append when text is shortened (default: "...")

    Returns:
        Original text if fits, otherwise shortened text with placeholder
    """
    if len(text) <= width:
        return text
    return text[: width - len(placeholder)] + placeholder


def to_camel_case(name: str) -> str:
    """Convert a string to CamelCase if it's not already.

    Handles snake_case, kebab-case, space-separated, and mixed cases.

    Args:
        name: String to convert to CamelCase

    Returns:
        String in CamelCase format
    """
    # Check if already in CamelCase
    if is_camel_case(name):
        return name

    # Replace common separators with spaces
    name = name.replace("_", " ").replace("-", " ")

    # Split into words and capitalize each
    words = name.split()

    # Handle empty string
    if not words:
        return name

    # Convert to CamelCase
    camel_case = "".join(word.capitalize() for word in words)

    return camel_case


def is_camel_case(name: str) -> bool:
    """Check if a string is already in CamelCase format.

    Args:
        name: String to check

    Returns:
        True if string is in CamelCase format, False otherwise
    """
    # CamelCase criteria:
    # - No spaces, underscores, or hyphens
    # - Starts with uppercase letter
    # - Contains at least one letter

    if not name or not name[0].isupper():
        return False

    if " " in name or "_" in name or "-" in name:
        return False

    # Check if it has proper capitalization pattern
    # (optional check for strict CamelCase)
    return name.isalnum()


def indent(text: str, indent_size: int = 4, indent_char: str = " ") -> str:
    """Indent each line in a string with the given indent size.

    Args:
        text: Text to indent
        indent_size: Number of indent characters per line (default: 4)
        indent_char: Character to use for indentation (default: space)

    Returns:
        Text with each non-empty line indented
    """
    lines = text.split("\n")
    indent_str = indent_char * indent_size
    indented_lines = [indent_str + line if line.strip() else line for line in lines]
    return "\n".join(indented_lines)
