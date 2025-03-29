from typing import Any, Dict

from markdown_it import MarkdownIt


def parse_markdown_to_dict(markdown_text: str) -> Dict[str, Any]:
    """
    Parse markdown text into a hierarchical dictionary structure (AST).

    Args:
        markdown_text: The markdown text to parse

    Returns:
        A dictionary representing the AST of the markdown text
    """
    # Initialize markdown parser
    md = MarkdownIt()
    tokens = md.parse(markdown_text)

    # Initialize root and stack for tracking hierarchy
    root = {"type": "root", "children": []}
    stack = [root]

    def get_current_level() -> int:
        """Get the heading level of the current container in the stack"""
        for item in reversed(stack):
            if "type" in item and item["type"].startswith("h"):
                return int(item["type"][1])
        return 0

    def close_until_level(target_level: int) -> None:
        """Pop items from stack until we reach the target level"""
        while len(stack) > 1 and get_current_level() >= target_level:
            stack.pop()

    i = 0
    list_counter = 0  # Counter for ordered list items
    while i < len(tokens):
        token = tokens[i]

        if token.type == "heading_open":
            level = int(token.tag[1])  # Extract level from h1, h2, etc.
            close_until_level(level)

            # Get heading text from next token
            heading_text = tokens[i + 1].content
            new_heading = {"type": f"h{level}", "text": heading_text, "children": []}
            stack[-1]["children"].append(new_heading)
            stack.append(new_heading)
            i += 2  # Skip the heading_close token

        elif token.type == "paragraph_open":
            paragraph_text = tokens[i + 1].content
            stack[-1]["children"].append({"type": "paragraph", "text": paragraph_text})
            i += 2  # Skip paragraph_close

        elif token.type == "bullet_list_open" or token.type == "ordered_list_open":
            new_list = {
                "type": "list",
                "children": [],
                "_ordered": token.type == "ordered_list_open",
            }
            stack[-1]["children"].append(new_list)
            stack.append(new_list)
            list_counter = 1  # Reset counter for ordered lists
            i += 1

        elif token.type == "list_item_open":
            item_text = ""
            j = i + 1
            while tokens[j].type != "list_item_close":
                if tokens[j].type == "inline":
                    item_text = tokens[j].content
                j += 1

            item = {"type": "list-item", "text": item_text}
            if stack[-1].get("_ordered", False):
                item["_number"] = list_counter
                list_counter += 1
            stack[-1]["children"].append(item)
            i = j + 1

        elif token.type in ["bullet_list_close", "ordered_list_close"]:
            stack.pop()
            i += 1

        elif token.type == "blockquote_open":
            quote_text = ""
            j = i + 1
            while tokens[j].type != "blockquote_close":
                if tokens[j].type == "inline":
                    quote_text = tokens[j].content
                j += 1

            stack[-1]["children"].append({"type": "quote", "text": quote_text})
            i = j + 1

        elif token.type == "fence":  # For code blocks
            stack[-1]["children"].append({"type": "code-block", "text": token.content})
            i += 1

        else:
            i += 1

    # Return the root node or its only child if it's a heading
    if len(root["children"]) == 1 and root["children"][0]["type"].startswith("h"):
        return root["children"][0]
    return root


def refresh_markdown_attributes(node: Dict[str, Any]) -> None:
    """
    Performs a DFS walk on the node tree to add markdown attributes to each node.
    This adds a 'markdown' field to each node with the markdown representation.

    Args:
        node: The node to process and update with markdown attributes
    """
    # Process children first (DFS)
    if "children" in node:
        for child in node["children"]:
            refresh_markdown_attributes(child)

    # Generate markdown for current node
    current_markdown = ""
    if node["type"].startswith("h"):
        level = int(node["type"][1])  # Extract number from h1, h2, etc.
        current_markdown = "#" * level + " " + node["text"]
    elif node["type"] == "paragraph":
        current_markdown = node["text"]
    elif node["type"] == "quote":
        current_markdown = "> " + node["text"]
    elif node["type"] == "code-block":
        current_markdown = node["text"]
    elif node["type"] == "list":
        # List nodes don't need their own text, they're containers
        pass
    elif node["type"] == "list-item":
        prefix = f"{node['_number']}. " if "_number" in node else "- "
        current_markdown = prefix + node["text"]

    # Combine current node's markdown with children's markdown
    markdown_parts = [current_markdown] if current_markdown else []
    for child in node.get("children", []):
        if "markdown" in child:
            markdown_parts.append(child["markdown"])

    node["markdown"] = "\n".join(markdown_parts).strip()

    # Clean up internal attributes
    node.pop("_ordered", None)
    node.pop("_number", None)


def markdown_to_ast(markdown: str) -> Dict[str, Any]:
    """
    Convert markdown text to an Abstract Syntax Tree (AST) representation.

    Args:
        markdown: The markdown text to convert

    Returns:
        A dictionary representing the AST of the markdown text with a 'document' root
    """
    tree = parse_markdown_to_dict(markdown)
    refresh_markdown_attributes(tree)

    # If tree is already a root node, convert it to a document node
    if tree.get("type") == "root":
        tree["type"] = "document"
        tree["text"] = ""
        return tree

    # Otherwise wrap the tree in a document node
    return {
        "type": "document",
        "text": "",
        "children": [tree] if isinstance(tree, dict) else tree.get("children", []),
        "markdown": markdown,
    }
