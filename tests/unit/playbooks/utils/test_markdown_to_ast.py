import pytest

from playbooks.utils.markdown_to_ast import (
    parse_markdown_to_dict,
    refresh_markdown_attributes,
    markdown_to_ast,
)


def test_parse_markdown_to_dict_headings():
    """Test parsing markdown headings into AST dictionary."""
    markdown_text = "# Heading 1\n## Heading 2\n### Heading 3\n#### Heading 4"

    ast = parse_markdown_to_dict(markdown_text)

    assert ast["type"] == "h1"
    assert ast["text"] == "Heading 1"
    assert len(ast["children"]) == 1
    assert ast["children"][0]["type"] == "h2"
    assert ast["children"][0]["text"] == "Heading 2"


def test_parse_markdown_to_dict_paragraphs():
    """Test parsing markdown paragraphs into AST dictionary."""
    markdown_text = (
        "This is paragraph 1.\n\nThis is paragraph 2.\n\nThis is paragraph 3."
    )

    ast = parse_markdown_to_dict(markdown_text)

    assert ast["type"] == "root"
    assert len(ast["children"]) == 3

    for i, child in enumerate(ast["children"]):
        assert child["type"] == "paragraph"
        assert child["text"] == f"This is paragraph {i+1}."


def test_parse_markdown_to_dict_lists():
    """Test parsing markdown lists into AST dictionary."""
    markdown_text = (
        "- Item 1\n- Item 2\n- Item 3\n\n1. Ordered 1\n2. Ordered 2\n3. Ordered 3"
    )

    ast = parse_markdown_to_dict(markdown_text)

    assert ast["type"] == "root"
    assert len(ast["children"]) == 2

    unordered_list = ast["children"][0]
    assert unordered_list["type"] == "list"
    assert unordered_list.get("_ordered", False) is False
    assert len(unordered_list["children"]) == 3

    for i, item in enumerate(unordered_list["children"]):
        assert item["type"] == "list-item"
        assert item["text"] == f"Item {i+1}"

    ordered_list = ast["children"][1]
    assert ordered_list["type"] == "list"
    assert ordered_list.get("_ordered", False) is True
    assert len(ordered_list["children"]) == 3

    for i, item in enumerate(ordered_list["children"]):
        assert item["type"] == "list-item"
        assert item["text"] == f"Ordered {i+1}"
        assert item["_number"] == i + 1


def test_parse_markdown_to_dict_nested_lists():
    """Test parsing markdown with properly nested lists into AST dictionary."""
    markdown_text = """- Level 1, Item 1
  - Level 2, Item 1
    - Level 3, Item 1
- Level 1, Item 2"""

    ast = parse_markdown_to_dict(markdown_text)

    assert ast["type"] == "root"
    assert len(ast["children"]) == 1

    list_node = ast["children"][0]
    assert list_node["type"] == "list"
    assert len(list_node["children"]) == 2

    level1_item1 = list_node["children"][0]
    assert level1_item1["type"] == "list-item"
    assert level1_item1["text"] == "Level 1, Item 1"

    # Verify that it has a nested list
    nested_lists = [
        child for child in level1_item1["children"] if child["type"] == "list"
    ]
    assert len(nested_lists) == 1

    level2_list = nested_lists[0]
    assert len(level2_list["children"]) == 1
    assert level2_list["children"][0]["text"] == "Level 2, Item 1"

    level3_lists = [
        child
        for child in level2_list["children"][0]["children"]
        if child["type"] == "list"
    ]
    assert len(level3_lists) == 1
    assert level3_lists[0]["children"][0]["text"] == "Level 3, Item 1"


def test_parse_markdown_to_dict_code_blocks():
    """Test parsing markdown code blocks into AST dictionary."""
    markdown_text = '```python\ndef hello_world():\n    print("Hello, World!")\n```'

    ast = parse_markdown_to_dict(markdown_text)

    assert ast["type"] == "root"
    assert len(ast["children"]) == 1

    code_block = ast["children"][0]
    assert code_block["type"] == "code-block"
    # Note: The actual implementation includes a newline at the end
    assert "def hello_world():" in code_block["text"]
    assert 'print("Hello, World!")' in code_block["text"]


def test_parse_markdown_to_dict_blockquotes():
    """Test parsing markdown blockquotes into AST dictionary."""
    markdown_text = "> This is a blockquote."

    ast = parse_markdown_to_dict(markdown_text)

    assert ast["type"] == "root"
    assert len(ast["children"]) == 1

    blockquote = ast["children"][0]
    assert blockquote["type"] == "quote"
    assert blockquote["text"] == "This is a blockquote."


def test_refresh_markdown_attributes():
    """Test refreshing markdown attributes in AST nodes."""
    # Create a simple AST structure
    ast = {
        "type": "h1",
        "text": "Heading 1",
        "children": [
            {"type": "paragraph", "text": "This is a paragraph."},
            {
                "type": "list",
                "_ordered": False,
                "children": [
                    {"type": "list-item", "text": "Item 1"},
                    {"type": "list-item", "text": "Item 2"},
                ],
            },
        ],
    }

    refresh_markdown_attributes(ast)

    # Check that markdown attributes were added
    assert "markdown" in ast
    assert ast["markdown"].startswith("# Heading 1")
    assert "This is a paragraph." in ast["markdown"]
    assert "- Item 1" in ast["markdown"]
    assert "- Item 2" in ast["markdown"]

    # Check that internal attributes were removed
    assert "_ordered" not in ast["children"][1]


def test_markdown_to_ast_simple():
    """Test converting simple markdown to AST."""
    markdown_text = "# Test Document\n\nThis is a test paragraph."

    ast = markdown_to_ast(markdown_text)

    assert ast["type"] == "document"
    assert ast["text"] == ""
    assert "children" in ast
    assert len(ast["children"]) >= 1

    # Find the heading
    h1 = None
    for node in ast["children"]:
        if node["type"] == "h1" and node["text"] == "Test Document":
            h1 = node
            break

    assert h1 is not None

    # The paragraph is actually a child of the h1 node in the implementation
    paragraph = None
    for node in h1["children"]:
        if node["type"] == "paragraph" and node["text"] == "This is a test paragraph.":
            paragraph = node
            break

    assert paragraph is not None


def test_markdown_to_ast_complex():
    """Test converting complex markdown with mixed elements to AST."""
    markdown_text = '# Complex Document\n\nThis is a paragraph with some content.\n\n- List item 1\n- List item 2\n\n> This is a blockquote.\n\n```python\ndef test_function():\n    return "test"\n```'

    ast = markdown_to_ast(markdown_text)

    assert ast["type"] == "document"
    assert "markdown" in ast

    # Check that the document has the h1 as a child
    h1 = None
    for node in ast["children"]:
        if node["type"] == "h1" and node["text"] == "Complex Document":
            h1 = node
            break

    assert h1 is not None

    # Check for paragraph - it's a child of h1 in the implementation
    paragraph = None
    for node in h1["children"]:
        if node["type"] == "paragraph" and "content" in node["text"]:
            paragraph = node
            break

    assert paragraph is not None

    # Check for list - it's a child of h1 in the implementation, not paragraph
    list_node = None
    for node in h1["children"]:
        if node["type"] == "list":
            list_node = node
            break

    assert list_node is not None
    assert len(list_node["children"]) == 2

    # Check for blockquote - it's a child of the list in the implementation
    blockquote = None
    for node in list_node["children"]:
        if node["type"] == "quote":
            blockquote = node
            break

    if blockquote is None:
        for node in h1["children"]:
            if node["type"] == "quote":
                blockquote = node
                break

    assert blockquote is not None

    # Check for code block - it's a child of h1 in the implementation, not blockquote
    # Blockquotes don't have children in the implementation
    code_block = None
    for node in h1["children"]:
        if node["type"] == "code-block":
            code_block = node
            break

    assert code_block is not None
    assert "def test_function():" in code_block["text"]


def test_markdown_to_ast_four_level_nested_lists():
    """Test converting markdown with 4-level deep nested lists to AST."""
    markdown_text = """# Four Level Nested Lists

- Level 1, Item 1
  - Level 2, Item 1
    - Level 3, Item 1
      - Level 4, Item 1
      - Level 4, Item 2
    - Level 3, Item 2
  - Level 2, Item 2
- Level 1, Item 2"""

    ast = markdown_to_ast(markdown_text)
    assert ast["type"] == "document"

    # Find the heading
    h1 = None
    for node in ast["children"]:
        if node["type"] == "h1" and node["text"] == "Four Level Nested Lists":
            h1 = node
            break

    assert h1 is not None

    # Find the list - it's a child of h1 in the implementation
    list_node = None
    for node in h1["children"]:
        if node["type"] == "list":
            list_node = node
            break

    assert list_node is not None
    assert len(list_node["children"]) == 2

    level1_item1 = list_node["children"][0]
    assert level1_item1["type"] == "list-item"
    assert level1_item1["text"] == "Level 1, Item 1"

    # Check for level 2 list
    level2_list = None
    for node in level1_item1["children"]:
        if node["type"] == "list":
            level2_list = node
            break

    assert level2_list is not None
    assert len(level2_list["children"]) == 2

    level2_item1 = level2_list["children"][0]
    assert level2_item1["text"] == "Level 2, Item 1"

    # Check for level 3 list
    level3_list = None
    for node in level2_item1["children"]:
        if node["type"] == "list":
            level3_list = node
            break

    assert level3_list is not None
    assert len(level3_list["children"]) == 2

    level3_item1 = level3_list["children"][0]
    assert level3_item1["text"] == "Level 3, Item 1"

    # Check for level 4 list
    level4_list = None
    for node in level3_item1["children"]:
        if node["type"] == "list":
            level4_list = node
            break

    assert level4_list is not None
    assert len(level4_list["children"]) == 2

    assert level4_list["children"][0]["text"] == "Level 4, Item 1"
    assert level4_list["children"][1]["text"] == "Level 4, Item 2"


def test_markdown_to_ast_mixed_list_types():
    """Test converting markdown with mixed ordered and unordered lists to AST."""
    markdown_text = "# Mixed Lists\n\n1. First ordered item\n2. Second ordered item\n3. Third ordered item\n\n- Unordered item 1\n- Unordered item 2"

    ast = markdown_to_ast(markdown_text)

    assert ast["type"] == "document"
    assert "markdown" in ast

    # Find the heading
    h1 = None
    for node in ast["children"]:
        if node["type"] == "h1" and node["text"] == "Mixed Lists":
            h1 = node
            break

    assert h1 is not None

    # Find the lists - they're children of h1 in the implementation
    lists = []
    for node in h1["children"]:
        if node["type"] == "list":
            lists.append(node)

    assert len(lists) == 2

    # Check ordered list - note: _ordered property is removed during refresh_markdown_attributes
    ordered_list = lists[0]
    assert ordered_list["type"] == "list"
    assert len(ordered_list["children"]) == 3

    # Check unordered list - note: _ordered property is removed during refresh_markdown_attributes
    unordered_list = lists[1]
    assert unordered_list["type"] == "list"
    # Don't check for _ordered property as it's removed during refresh_markdown_attributes
    assert len(unordered_list["children"]) == 2


def test_markdown_to_ast_with_proper_nested_lists():
    """Test parsing markdown with proper nested list syntax after implementation fix."""
    markdown_text = """# Four Level Nested Lists

- Level 1, Item 1
  - Level 2, Item 1
    - Level 3, Item 1
      - Level 4, Item 1
      - Level 4, Item 2
    - Level 3, Item 2
  - Level 2, Item 2
- Level 1, Item 2"""

    ast = markdown_to_ast(markdown_text)
    assert ast["type"] == "document"

    # Find the heading
    h1 = None
    for node in ast["children"]:
        if node["type"] == "h1" and node["text"] == "Four Level Nested Lists":
            h1 = node
            break

    assert h1 is not None

    # Find the list - it's a child of h1 in the implementation
    list_node = None
    for node in h1["children"]:
        if node["type"] == "list":
            list_node = node
            break

    assert list_node is not None

    # Verify the markdown contains proper nested list structure
    assert "markdown" in ast
    assert "- Level 1, Item 1" in ast["markdown"]

    # Check that the nested lists are properly indented in the markdown output
    markdown_lines = ast["markdown"].split("\n")
    indented_lines = [
        line
        for line in markdown_lines
        if "Level 2" in line or "Level 3" in line or "Level 4" in line
    ]

    for line in indented_lines:
        if "Level 2" in line:
            assert line.startswith("  - ")
        elif "Level 3" in line:
            assert line.startswith("    - ")
        elif "Level 4" in line:
            assert line.startswith("      - ")


def test_parse_markdown_to_dict_multi_paragraph_list_items():
    """Test parsing markdown with list items containing multiple paragraphs."""
    markdown_text = """- List item with
  multiple paragraphs

  Second paragraph in the same list item
- Another list item"""

    ast = parse_markdown_to_dict(markdown_text)

    assert ast["type"] == "root"
    assert len(ast["children"]) == 1

    list_node = ast["children"][0]
    assert list_node["type"] == "list"
    assert len(list_node["children"]) == 2

    multi_para_item = list_node["children"][0]
    assert multi_para_item["type"] == "list-item"
    assert "List item with\nmultiple paragraphs" in multi_para_item["text"]
    assert "Second paragraph in the same list item" in multi_para_item["text"]

    second_item = list_node["children"][1]
    assert second_item["type"] == "list-item"
    assert second_item["text"] == "Another list item"


def test_markdown_to_ast_multi_paragraph_list_items():
    """Test converting markdown with list items containing multiple paragraphs to AST."""
    markdown_text = """# Multiple Paragraph List Items

- List item with
  multiple paragraphs

  Second paragraph in the same list item
- Another list item"""

    ast = markdown_to_ast(markdown_text)
    assert "markdown" in ast

    # Debug: Print the actual markdown output
    print("\nActual markdown output:")
    for i, line in enumerate(ast["markdown"].split("\n")):
        print(f"{i}: {line}")

    # Verify the markdown output properly formats the multiple paragraphs
    markdown_lines = ast["markdown"].split("\n")
    # Check for list item text across lines (line 2 has "List item with", line 3 has "multiple paragraphs")
    assert any("List item with" in line for line in markdown_lines)
    assert any("multiple paragraphs" in line for line in markdown_lines)
    assert any(
        "Second paragraph in the same list item" in line for line in markdown_lines
    )


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
