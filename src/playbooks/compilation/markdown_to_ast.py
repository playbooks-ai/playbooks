from typing import Any, Dict, Optional

from markdown_it import MarkdownIt
from markdown_it.token import Token


def parse_markdown_to_dict(markdown_text: str) -> Dict[str, Any]:
    """
    Parse markdown text into a hierarchical dictionary structure (AST)
    with line numbers.

    Args:
        markdown_text: The markdown text to parse

    Returns:
        A dictionary representing the AST of the markdown text with
        line numbers
    """
    # Initialize markdown parser with line numbers and disable setext headings
    # to prevent YAML-like content from being interpreted as headings
    md = MarkdownIt()
    md.disable(
        ["lheading"]
    )  # Disable setext-style headings (underline with --- or ===)
    tokens = md.parse(markdown_text)

    # Initialize root and stack for tracking hierarchy
    root = {"type": "root", "children": [], "line_number": 1}
    stack = [root]

    def get_current_level() -> int:
        """Get the heading level of the current container in the stack"""
        for item in reversed(stack):
            if (
                "type" in item
                and item["type"].startswith("h")
                and len(item["type"]) == 2
                and item["type"][1].isdigit()
            ):
                return int(item["type"][1])
        return 0

    def close_until_level(target_level: int) -> None:
        """Pop items from stack until we reach the target level"""
        while len(stack) > 1 and get_current_level() >= target_level:
            stack.pop()

    def get_line_number(token: Token) -> int:
        """Get the 1-indexed line number for a token"""
        if hasattr(token, "map") and token.map:
            return token.map[0] + 1  # Convert to 1-indexed
        return 1

    i = 0
    list_counter = 0  # Counter for ordered list items
    while i < len(tokens):
        token = tokens[i]

        if token.type == "html_block":
            stack[-1]["children"].append(
                {
                    "type": "html_block",
                    "content": token.content,
                    "line_number": get_line_number(token),
                }
            )
            i += 1

        elif token.type == "heading_open":
            level = int(token.tag[1])  # Extract level from h1, h2, etc.
            close_until_level(level)

            # Get heading text from next token
            heading_text = tokens[i + 1].content
            line_number = get_line_number(token)

            new_heading = {
                "type": f"h{level}",
                "text": heading_text,
                "children": [],
                "line_number": line_number,
            }
            stack[-1]["children"].append(new_heading)
            stack.append(new_heading)
            i += 2  # Skip the heading_close token

        elif token.type == "paragraph_open":
            paragraph_text = tokens[i + 1].content
            line_number = get_line_number(token)

            if stack[-1]["type"] == "list-item":
                if not stack[-1]["text"]:
                    stack[-1]["text"] = paragraph_text
                else:
                    stack[-1]["text"] += "\n\n" + paragraph_text
            else:
                stack[-1]["children"].append(
                    {
                        "type": "paragraph",
                        "text": paragraph_text,
                        "line_number": line_number,
                    }
                )
            i += 2  # Skip paragraph_close

        elif token.type == "bullet_list_open" or token.type == "ordered_list_open":
            line_number = get_line_number(token)
            new_list = {
                "type": "list",
                "children": [],
                "_ordered": token.type == "ordered_list_open",
                "line_number": line_number,
            }
            stack[-1]["children"].append(new_list)
            stack.append(new_list)
            list_counter = 1  # Reset counter for ordered lists
            i += 1

        elif token.type == "list_item_open":
            line_number = get_line_number(token)
            item = {
                "type": "list-item",
                "text": "",
                "children": [],
                "line_number": line_number,
            }
            if stack[-1].get("_ordered", False):
                item["_number"] = list_counter
                list_counter += 1

            stack[-1]["children"].append(item)
            stack.append(item)
            i += 1

        elif token.type == "list_item_close":
            stack.pop()
            i += 1

        elif token.type in ["bullet_list_close", "ordered_list_close"]:
            stack.pop()
            i += 1

        elif token.type == "blockquote_open":
            line_number = get_line_number(token)
            quote_text = ""
            j = i + 1
            while tokens[j].type != "blockquote_close":
                if tokens[j].type == "inline":
                    quote_text = tokens[j].content
                j += 1

            stack[-1]["children"].append(
                {"type": "quote", "text": quote_text, "line_number": line_number}
            )
            i = j + 1

        elif token.type == "fence":  # For code blocks
            line_number = get_line_number(token)
            code_block = {
                "type": "code-block",
                "text": token.content,
                "line_number": line_number,
            }
            # Preserve language/filename from fence info
            if token.info:
                code_block["language"] = token.info
            stack[-1]["children"].append(code_block)
            i += 1

        elif token.type == "hr":  # Handle horizontal rules (---)
            line_number = get_line_number(token)
            stack[-1]["children"].append(
                {
                    "type": "hr",
                    "text": "---",
                    "line_number": line_number,
                }
            )
            i += 1

        elif token.type == "comment":
            line_number = get_line_number(token)
            stack[-1]["children"].append(
                {"type": "comment", "text": token.content, "line_number": line_number}
            )
            i += 1
        else:
            i += 1

    # Return the root node or its only child if it's a heading
    if (
        len(root["children"]) == 1
        and root["children"][0]["type"].startswith("h")
        and len(root["children"][0]["type"]) == 2
        and root["children"][0]["type"][1].isdigit()
    ):
        return root["children"][0]
    return root


def refresh_markdown_attributes(node: Dict[str, Any]) -> None:
    """
    Performs a DFS walk on the node tree to add markdown attributes to
    each node. This adds a 'markdown' field to each node with the
    markdown representation. Line numbers are preserved during this process.

    Args:
        node: The node to process and update with markdown attributes
    """
    # Process children first (DFS)
    if "children" in node:
        for child in node["children"]:
            refresh_markdown_attributes(child)

    # Generate markdown for current node
    current_markdown = ""
    markdown_prefix = ""
    markdown_suffix = ""
    if (
        node["type"].startswith("h")
        and len(node["type"]) == 2
        and node["type"][1].isdigit()
    ):
        level = int(node["type"][1])  # Extract number from h1, h2, etc.
        if level <= 3:
            markdown_prefix = "\n"
        if level == 2:
            markdown_suffix = "\n\n"
        current_markdown = "#" * level + " " + node["text"]
    elif node["type"] == "paragraph":
        current_markdown = node["text"]
    elif node["type"] == "quote":
        current_markdown = "> " + node["text"]
    elif node["type"] == "code-block":
        markdown_prefix = "\n"
        language = node.get("language", "")
        current_markdown = f"```{language}\n" + node["text"] + "\n```"
    elif node["type"] == "hr":
        current_markdown = "---"
    elif node["type"] == "list":
        # List nodes don't need their own text, they're containers
        pass
    elif node["type"] == "list-item":
        prefix = f"{node['_number']}. " if "_number" in node else "- "

        # Handle multiple paragraphs in list items
        if "\n\n" in node["text"]:
            paragraphs = node["text"].split("\n\n")
            first_para = prefix + paragraphs[0]
            indent = " " * len(prefix)
            rest_paras = [indent + p for p in paragraphs[1:]]
            current_markdown = "\n\n".join([first_para] + rest_paras)
        else:
            current_markdown = prefix + node["text"]

        children_markdown = []
        for child in node.get("children", []):
            if "markdown" in child and child["type"] == "list":
                # Indent each line of the nested list's markdown
                indented_lines = []
                for line in child["markdown"].split("\n"):
                    if line:
                        indented_lines.append("  " + line)
                if indented_lines:
                    children_markdown.append("\n".join(indented_lines))

        if children_markdown:
            current_markdown += "\n" + "\n".join(children_markdown)
    elif node["type"] == "html_block":
        current_markdown = node["content"]

    # Combine current node's markdown with children's markdown
    markdown_parts = [current_markdown] if current_markdown else []
    for child in node.get("children", []):
        if "markdown" in child:
            # For list-item nodes, skip nested lists since they're already handled above
            if node["type"] == "list-item" and child["type"] == "list":
                continue
            markdown_parts.append(child["markdown"])

    node["markdown"] = (
        markdown_prefix + "\n".join(markdown_parts).strip() + markdown_suffix
    )

    # Clean up internal attributes
    node.pop("_ordered", None)
    node.pop("_number", None)


def _set_source_file_path_recursively(
    node: Dict[str, Any], source_file_path: str
) -> None:
    """
    Recursively set source_file_path on all nodes in the AST.

    Args:
        node: The AST node to process
        source_file_path: The source file path to set
    """
    if isinstance(node, dict):
        node["source_file_path"] = source_file_path

        # Process children
        if "children" in node and isinstance(node["children"], list):
            for child in node["children"]:
                _set_source_file_path_recursively(child, source_file_path)


def markdown_to_ast(
    markdown: str, source_file_path: Optional[str] = None
) -> Dict[str, Any]:
    """Convert markdown text to an Abstract Syntax Tree (AST) representation.

    Converts markdown to AST with line numbers and source file path.
    Refreshes markdown attributes and ensures document structure.

    Args:
        markdown: The markdown text to convert
        source_file_path: Optional path to the source file (typically .pbasm cache file)

    Returns:
        Dictionary representing the AST with 'document' root, line numbers,
        and source file path on all nodes
    """
    tree = parse_markdown_to_dict(markdown)
    refresh_markdown_attributes(tree)

    # If tree is already a root node, convert it to a document node
    if tree.get("type") == "root":
        tree["type"] = "document"
        tree["text"] = ""
        tree["markdown"] = markdown  # Preserve original markdown

        # Set source file path on all nodes if provided
        if source_file_path:
            _set_source_file_path_recursively(tree, source_file_path)

        return tree

    # Otherwise wrap the tree in a document node
    children = [tree] if isinstance(tree, dict) else tree.get("children", [])
    document_node = {
        "type": "document",
        "text": "",
        "children": children,
        "markdown": markdown,
        "line_number": 1,
    }

    # Set source file path on all nodes if provided
    if source_file_path:
        _set_source_file_path_recursively(document_node, source_file_path)

    return document_node
