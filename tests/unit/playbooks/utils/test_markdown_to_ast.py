import pytest

from playbooks.utils.markdown_to_ast import (
    markdown_to_ast,
    parse_markdown_to_dict,
    refresh_markdown_attributes,
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
    markdown_text = (
        "```python\n" "def hello_world():\n" '    print("Hello, World!")\n' "```"
    )

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
    markdown_text = (
        "# Complex Document\n\n"
        "This is a paragraph with some content.\n\n"
        "- List item 1\n- List item 2\n\n"
        "> This is a blockquote.\n\n"
        "```python\n"
        "def test_function():\n"
        '    return "test"\n'
        "```"
    )

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
    markdown_text = (
        "# Mixed Lists\n\n"
        "1. First ordered item\n"
        "2. Second ordered item\n"
        "3. Third ordered item\n\n"
        "- Unordered item 1\n"
        "- Unordered item 2"
    )

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


# ============================================================================
# NEW TEST CASES FOR LINE NUMBER TRACKING
# ============================================================================


def test_line_numbers_simple_headings():
    """Test that line numbers are correctly assigned to headings."""
    markdown_text = """# Heading 1
## Heading 2
### Heading 3"""

    ast = parse_markdown_to_dict(markdown_text)

    assert ast["type"] == "h1"
    assert ast["line_number"] == 1
    assert ast["text"] == "Heading 1"

    # Check nested headings
    h2 = ast["children"][0]
    assert h2["type"] == "h2"
    assert h2["line_number"] == 2
    assert h2["text"] == "Heading 2"

    h3 = h2["children"][0]
    assert h3["type"] == "h3"
    assert h3["line_number"] == 3
    assert h3["text"] == "Heading 3"


def test_line_numbers_with_paragraphs():
    """Test line numbers for paragraphs."""
    markdown_text = """# Document Title

This is the first paragraph.

This is the second paragraph.

This is the third paragraph."""

    ast = markdown_to_ast(markdown_text)

    # Find the h1
    h1 = ast["children"][0]
    assert h1["type"] == "h1"
    assert h1["line_number"] == 1

    # Check paragraphs
    paragraphs = [child for child in h1["children"] if child["type"] == "paragraph"]
    assert len(paragraphs) == 3

    assert paragraphs[0]["line_number"] == 3
    assert paragraphs[0]["text"] == "This is the first paragraph."

    assert paragraphs[1]["line_number"] == 5
    assert paragraphs[1]["text"] == "This is the second paragraph."

    assert paragraphs[2]["line_number"] == 7
    assert paragraphs[2]["text"] == "This is the third paragraph."


def test_line_numbers_with_lists():
    """Test line numbers for list items."""
    markdown_text = """# Lists

- First item
- Second item
- Third item

1. Ordered first
2. Ordered second"""

    ast = markdown_to_ast(markdown_text)

    h1 = ast["children"][0]
    assert h1["line_number"] == 1

    lists = [child for child in h1["children"] if child["type"] == "list"]
    assert len(lists) == 2

    # Unordered list
    unordered = lists[0]
    assert unordered["line_number"] == 3
    assert len(unordered["children"]) == 3

    assert unordered["children"][0]["line_number"] == 3
    assert unordered["children"][0]["text"] == "First item"

    assert unordered["children"][1]["line_number"] == 4
    assert unordered["children"][1]["text"] == "Second item"

    assert unordered["children"][2]["line_number"] == 5
    assert unordered["children"][2]["text"] == "Third item"

    # Ordered list
    ordered = lists[1]
    assert ordered["line_number"] == 7
    assert ordered["children"][0]["line_number"] == 7
    assert ordered["children"][1]["line_number"] == 8


def test_line_numbers_nested_lists():
    """Test line numbers for nested lists."""
    markdown_text = """### Steps
- 01:QUE Introduce Clover and yourself
- 02:EXE $relevant_information:list = []
- 03:CND While conversation is active
  - 03.01:CND If user is doing chitchat
    - 03.01.01:QUE Reply to the user with professional chitchat
  - 03.02:CND Otherwise
    - 03.02.01:QUE AnswerQuestionUsingKnowledgeBase()
    - 03.02.02:YLD call
"""

    ast = markdown_to_ast(markdown_text)

    h3 = ast["children"][0]
    assert h3["line_number"] == 1

    li = h3["children"][0]
    assert li["line_number"] == 2

    assert "01:QUE" in li["children"][0]["text"]
    assert li["children"][0]["line_number"] == 2

    assert "02:EXE" in li["children"][1]["text"]
    assert li["children"][1]["line_number"] == 3

    assert "03:CND" in li["children"][2]["text"]
    assert li["children"][2]["line_number"] == 4

    li2 = li["children"][2]["children"][0]
    assert "03.01:CND" in li2["children"][0]["text"]
    assert li2["children"][0]["line_number"] == 5

    li3 = li2["children"][0]["children"][0]
    assert "03.01.01:QUE" in li3["children"][0]["text"]
    assert li3["children"][0]["line_number"] == 6


def test_line_numbers_code_blocks():
    """Test line numbers for code blocks."""
    markdown_text = """# Code Examples

Here's some code:

```python
def hello():
    print("Hello, World!")
```

And more text."""

    ast = markdown_to_ast(markdown_text)

    h1 = ast["children"][0]

    # Find paragraph
    para1 = h1["children"][0]
    assert para1["type"] == "paragraph"
    assert para1["line_number"] == 3

    # Find code block
    code_block = h1["children"][1]
    assert code_block["type"] == "code-block"
    assert code_block["line_number"] == 5

    # Find last paragraph
    para2 = h1["children"][2]
    assert para2["type"] == "paragraph"
    assert para2["line_number"] == 10


def test_line_numbers_blockquotes():
    """Test line numbers for blockquotes."""
    markdown_text = """# Quotes

> This is a quote.

> This is another quote
> that spans multiple lines.

Regular text."""

    ast = markdown_to_ast(markdown_text)

    h1 = ast["children"][0]

    # First quote
    quote1 = h1["children"][0]
    assert quote1["type"] == "quote"
    assert quote1["line_number"] == 3
    assert quote1["text"] == "This is a quote."

    # Second quote
    quote2 = h1["children"][1]
    assert quote2["type"] == "quote"
    assert quote2["line_number"] == 5

    # Regular paragraph
    para = h1["children"][2]
    assert para["type"] == "paragraph"
    assert para["line_number"] == 8


def test_line_numbers_playbook_format():
    """Test line numbers for a typical playbook format."""
    markdown_text = """# PersonalizedGreeting
This program greets the user by name.

## Greet() -> None
Main greeting routine.

### Triggers
- T1:BGN At the beginning

### Steps
- Ask the user for their name
- Say hello to the user
- Exit the program"""

    ast = markdown_to_ast(markdown_text)

    # Document root
    assert ast["line_number"] == 1

    # H1
    h1 = ast["children"][0]
    assert h1["type"] == "h1"
    assert h1["line_number"] == 1
    assert h1["text"] == "PersonalizedGreeting"

    # Description paragraph
    desc = h1["children"][0]
    assert desc["type"] == "paragraph"
    assert desc["line_number"] == 2

    # H2 (Playbook)
    h2 = h1["children"][1]
    assert h2["type"] == "h2"
    assert h2["line_number"] == 4
    assert h2["text"] == "Greet() -> None"

    # Playbook description
    pb_desc = h2["children"][0]
    assert pb_desc["type"] == "paragraph"
    assert pb_desc["line_number"] == 5

    # H3 sections
    h3_triggers = h2["children"][1]
    assert h3_triggers["type"] == "h3"
    assert h3_triggers["line_number"] == 7
    assert h3_triggers["text"] == "Triggers"

    # Triggers list
    triggers_list = h3_triggers["children"][0]
    assert triggers_list["type"] == "list"
    assert triggers_list["line_number"] == 8
    assert triggers_list["children"][0]["line_number"] == 8

    # Steps section
    h3_steps = h2["children"][2]
    assert h3_steps["type"] == "h3"
    assert h3_steps["line_number"] == 10
    assert h3_steps["text"] == "Steps"

    # Steps list
    steps_list = h3_steps["children"][0]
    assert steps_list["type"] == "list"
    assert steps_list["line_number"] == 11
    assert steps_list["children"][0]["line_number"] == 11
    assert steps_list["children"][1]["line_number"] == 12
    assert steps_list["children"][2]["line_number"] == 13


def test_line_numbers_empty_lines():
    """Test that empty lines don't affect line number tracking."""
    markdown_text = """# Title


## Subtitle



### Sub-subtitle"""

    ast = parse_markdown_to_dict(markdown_text)

    assert ast["line_number"] == 1

    h2 = ast["children"][0]
    assert h2["line_number"] == 4

    h3 = h2["children"][0]
    assert h3["line_number"] == 8


def test_line_numbers_complex_document():
    """Test line numbers in a complex document with mixed content."""
    markdown_text = """# Complex Document

This is an introduction.

## Section 1

Content for section 1.

- List item 1
  - Nested item 1.1
  - Nested item 1.2
- List item 2

```python
# Code block
x = 42i
```

## Section 2

> A quote in section 2

Final paragraph."""

    ast = markdown_to_ast(markdown_text)

    h1 = ast["children"][0]
    assert h1["line_number"] == 1

    # Introduction
    intro = h1["children"][0]
    assert intro["line_number"] == 3

    # Section 1
    section1 = h1["children"][1]
    assert section1["line_number"] == 5
    assert section1["type"] == "h2"

    # Content in section 1
    content1 = section1["children"][0]
    assert content1["line_number"] == 7

    # List in section 1
    list1 = section1["children"][1]
    assert list1["line_number"] == 9

    # Code block
    code = section1["children"][2]
    assert code["type"] == "code-block"
    assert code["line_number"] == 14

    # Section 2
    section2 = h1["children"][2]
    assert section2["line_number"] == 19
    assert section2["type"] == "h2"

    # Quote in section 2
    quote = section2["children"][0]
    assert quote["line_number"] == 21

    # Final paragraph
    final = section2["children"][1]
    assert final["line_number"] == 23


def test_line_numbers_preserved_after_refresh():
    """Test that line numbers are preserved after refresh_markdown_attributes."""
    markdown_text = """# Test
## Subtest
- Item 1
- Item 2"""

    ast = parse_markdown_to_dict(markdown_text)

    # Store original line numbers
    h1_line = ast["line_number"]
    h2_line = ast["children"][0]["line_number"]
    list_line = ast["children"][0]["children"][0]["line_number"]

    # Refresh markdown attributes
    refresh_markdown_attributes(ast)

    # Verify line numbers are preserved
    assert ast["line_number"] == h1_line
    assert ast["children"][0]["line_number"] == h2_line
    assert ast["children"][0]["children"][0]["line_number"] == list_line


def test_line_numbers_multi_agent_pbasm(test_data_dir):
    """Test line numbers for multi-agent.pbasm file with multiple agents and playbooks."""
    # Read the actual multi-agent.pbasm file
    with open(test_data_dir / "multi-agent.pbasm", "r") as f:
        markdown_text = f.read()

    ast = markdown_to_ast(markdown_text)

    # The document should have two main agents (h1 elements)
    h1_nodes = [child for child in ast["children"] if child["type"] == "h1"]
    assert len(h1_nodes) == 2

    # First agent: FirstAgent
    first_agent = h1_nodes[0]
    assert first_agent["text"] == "FirstAgent"
    assert first_agent["line_number"] == 1

    # Second agent: CountryInfo
    country_info = h1_nodes[1]
    assert country_info["text"] == "CountryInfo"
    assert country_info["line_number"] == 37

    # Check playbooks in FirstAgent
    first_agent_playbooks = [
        child for child in first_agent["children"] if child["type"] == "h2"
    ]
    assert len(first_agent_playbooks) == 1

    # X($num=10) -> None playbook
    x_playbook = first_agent_playbooks[0]
    assert x_playbook["text"] == "X($num=10) -> None"
    assert x_playbook["line_number"] == 12

    # Check playbooks in CountryInfo agent
    country_info_playbooks = [
        child for child in country_info["children"] if child["type"] == "h2"
    ]
    assert len(country_info_playbooks) == 3

    # LocalPB() -> None
    local_pb = country_info_playbooks[0]
    assert local_pb["text"] == "LocalPB() -> None"
    assert local_pb["line_number"] == 48

    # public: GetCountryPopulation($country) -> float
    get_population = country_info_playbooks[1]
    assert get_population["text"] == "public: GetCountryPopulation($country) -> float"
    assert get_population["line_number"] == 54

    # public:GetCountrySecret($country) -> str
    get_secret = country_info_playbooks[2]
    assert get_secret["text"] == "public:GetCountrySecret($country) -> str"
    assert get_secret["line_number"] == 61

    # Check some h3 sections (Triggers, Steps)
    # X playbook's Triggers
    x_triggers = [
        child
        for child in x_playbook["children"]
        if child["type"] == "h3" and child["text"] == "Triggers"
    ]
    assert len(x_triggers) == 1
    assert x_triggers[0]["line_number"] == 14

    # X playbook's Steps
    x_steps = [
        child
        for child in x_playbook["children"]
        if child["type"] == "h3" and child["text"] == "Steps"
    ]
    assert len(x_steps) == 1
    assert x_steps[0]["line_number"] == 16

    # GetCountrySecret's Triggers
    secret_triggers = [
        child
        for child in get_secret["children"]
        if child["type"] == "h3" and child["text"] == "Triggers"
    ]
    assert len(secret_triggers) == 1
    assert secret_triggers[0]["line_number"] == 63

    # Check code blocks
    # Python code block in FirstAgent
    first_agent_code_blocks = [
        child for child in first_agent["children"] if child["type"] == "code-block"
    ]
    assert len(first_agent_code_blocks) >= 1
    assert first_agent_code_blocks[0]["line_number"] == 4

    # Python code block in CountryInfo
    country_info_code_blocks = [
        child for child in country_info["children"] if child["type"] == "code-block"
    ]
    assert len(country_info_code_blocks) >= 1
    assert country_info_code_blocks[0]["line_number"] == 40


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
