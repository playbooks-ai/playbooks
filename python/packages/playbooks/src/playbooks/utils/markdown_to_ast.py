from typing import Any, Dict

from markdown_it import MarkdownIt


def parse_markdown_to_dict(markdown_text: str) -> Dict[str, Any]:
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
            list_type = "list"
            list_counter = 1  # Reset counter for ordered lists
            new_list = {
                "type": list_type,
                "children": [],
                "_ordered": token.type == "ordered_list_open",
            }
            stack[-1]["children"].append(new_list)
            stack.append(new_list)
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

    # Remove root wrapper if there's only one top-level heading
    if len(root["children"]) == 1 and root["children"][0]["type"].startswith("h"):
        return root["children"][0]
    return root


def refresh_markdown_attributes(node: Dict[str, Any]) -> None:
    """
    Performs a DFS walk on the node tree to add markdown attributes.
    Returns the markdown string for the current node and all its children.
    """
    # Process children first (DFS)
    children_markdown = ""
    if "children" in node:
        for child in node["children"]:
            refresh_markdown_attributes(child)

    # Generate markdown for current node
    current_markdown = ""
    if node["type"].startswith("h"):
        level = node["type"][1]  # Extract number from h1, h2, etc.
        current_markdown = "#" * int(level) + " " + node["text"]

    elif node["type"] == "paragraph":
        current_markdown = node["text"]

    elif node["type"] == "quote":
        current_markdown = "> " + node["text"]

    elif node["type"] == "code-block":
        current_markdown = node["text"]

    elif node["type"] == "list":
        current_markdown = children_markdown.strip()

    elif node["type"] == "list-item":
        if "_number" in node:  # Ordered list item
            current_markdown = f"{node['_number']}. {node['text']}"
        else:  # Unordered list item
            current_markdown = f"- {node['text']}"

    # Combine current node's markdown with children's markdown
    full_markdown = [current_markdown]
    for child in node.get("children", []):
        full_markdown.append(child["markdown"])
    full_markdown = "\n".join(full_markdown)

    # Add markdown attribute to node
    node["markdown"] = full_markdown.strip()

    # Clean up internal attributes
    node.pop("_ordered", None)
    node.pop("_number", None)


def markdown_to_ast(markdown: str) -> Dict[str, Any]:
    tree = parse_markdown_to_dict(markdown)
    refresh_markdown_attributes(tree)

    # If tree is already a root/document node, just change its type and add text field
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
