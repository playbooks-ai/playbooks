"""Utility functions for counting tokens using tiktoken."""

import json
from typing import Dict, List, Union

import tiktoken


def get_token_count(text: str, model: str = "gpt-4") -> int:
    """
    Count the number of tokens in a text string using tiktoken.

    Args:
        text: The text to count tokens for
        model: The model to use for tokenization (default: gpt-4)

    Returns:
        The number of tokens in the text
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except KeyError:
        # Fallback to cl100k_base encoding if model not found
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))


def get_messages_token_count(
    messages: List[Dict[str, str]], model: str = "gpt-4"
) -> int:
    """
    Count the total number of tokens in a list of messages.

    Args:
        messages: List of message dictionaries with 'role' and 'content' keys
        model: The model to use for tokenization (default: gpt-4)

    Returns:
        The total number of tokens in all messages
    """
    total_tokens = 0

    for message in messages:
        # Count tokens for the message content
        content = message.get("content", "")
        total_tokens += get_token_count(content, model)

        # Add tokens for message structure (role, etc.)
        # OpenAI's ChatML format adds some overhead per message
        total_tokens += 4  # Approximate overhead per message

        # Handle name field if present
        if "name" in message:
            total_tokens += 1

    # Add tokens for conversation structure
    total_tokens += 2  # Approximate overhead for the conversation

    return total_tokens


def get_dict_token_count(data: Union[Dict, List], model: str = "gpt-4") -> int:
    """
    Count the number of tokens in a dictionary or list by converting to JSON.

    Args:
        data: The dictionary or list to count tokens for
        model: The model to use for tokenization (default: gpt-4)

    Returns:
        The number of tokens in the JSON representation
    """
    json_str = json.dumps(data, indent=2)
    return get_token_count(json_str, model)
