import unittest

from playbooks.markdown_to_ast import markdown_to_ast


class TestMarkdownToAst(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_simple_heading(self):
        markdown = "# Hello World"
        ast = markdown_to_ast(markdown)
        expected = {
            "type": "h1",
            "text": "Hello World",
            "children": [],
            "markdown": "# Hello World",
        }
        self.assertEqual(ast, expected)

    def test_nested_headings(self):
        markdown = """# Main Title
## Subtitle
### Sub-subtitle"""
        ast = markdown_to_ast(markdown)
        expected = {
            "type": "h1",
            "text": "Main Title",
            "children": [
                {
                    "type": "h2",
                    "text": "Subtitle",
                    "children": [
                        {
                            "type": "h3",
                            "text": "Sub-subtitle",
                            "children": [],
                            "markdown": "### Sub-subtitle",
                        }
                    ],
                    "markdown": "## Subtitle\n### Sub-subtitle",
                }
            ],
            "markdown": "# Main Title\n## Subtitle\n### Sub-subtitle",
        }
        self.assertEqual(ast, expected)

    def test_bullet_list(self):
        markdown = """- Item 1
- Item 2
- Item 3"""
        ast = markdown_to_ast(markdown)
        expected = {
            "type": "root",
            "children": [
                {
                    "type": "list",
                    "children": [
                        {"type": "list-item", "text": "Item 1", "markdown": "- Item 1"},
                        {"type": "list-item", "text": "Item 2", "markdown": "- Item 2"},
                        {"type": "list-item", "text": "Item 3", "markdown": "- Item 3"},
                    ],
                    "markdown": "- Item 1\n- Item 2\n- Item 3",
                }
            ],
            "markdown": "- Item 1\n- Item 2\n- Item 3",
        }
        self.assertEqual(ast, expected)

    def test_ordered_list(self):
        markdown = """1. First
2. Second
3. Third"""
        ast = markdown_to_ast(markdown)
        expected = {
            "type": "root",
            "children": [
                {
                    "type": "list",
                    "children": [
                        {"type": "list-item", "text": "First", "markdown": "1. First"},
                        {
                            "type": "list-item",
                            "text": "Second",
                            "markdown": "2. Second",
                        },
                        {"type": "list-item", "text": "Third", "markdown": "3. Third"},
                    ],
                    "markdown": "1. First\n2. Second\n3. Third",
                }
            ],
            "markdown": "1. First\n2. Second\n3. Third",
        }
        self.assertEqual(ast, expected)

    def test_paragraph(self):
        markdown = "This is a simple paragraph."
        ast = markdown_to_ast(markdown)
        expected = {
            "type": "root",
            "children": [
                {
                    "type": "paragraph",
                    "text": "This is a simple paragraph.",
                    "markdown": "This is a simple paragraph.",
                }
            ],
            "markdown": "This is a simple paragraph.",
        }
        self.assertEqual(ast, expected)

    def test_mixed_content(self):
        markdown = """# Title
This is a paragraph.

## Subtitle
- List item 1
- List item 2"""
        ast = markdown_to_ast(markdown)
        expected = {
            "type": "h1",
            "text": "Title",
            "children": [
                {
                    "type": "paragraph",
                    "text": "This is a paragraph.",
                    "markdown": "This is a paragraph.",
                },
                {
                    "type": "h2",
                    "text": "Subtitle",
                    "children": [
                        {
                            "type": "list",
                            "children": [
                                {
                                    "type": "list-item",
                                    "text": "List item 1",
                                    "markdown": "- List item 1",
                                },
                                {
                                    "type": "list-item",
                                    "text": "List item 2",
                                    "markdown": "- List item 2",
                                },
                            ],
                            "markdown": "- List item 1\n- List item 2",
                        }
                    ],
                    "markdown": "## Subtitle\n- List item 1\n- List item 2",
                },
            ],
            "markdown": "# Title\nThis is a paragraph.\n## Subtitle\n- List item 1\n- List item 2",
        }
        self.assertEqual(ast, expected)

    def test_hello_playbook(self):
        markdown = """# HelloWorld Agent
This is a simple Hello World agent.

## HelloWorld

### Trigger
When the user starts a conversation or asks for a greeting.

### Steps
- Greet the user with a friendly "Hello, World!" message.
- Explain that this is a demonstration of a simple Hello World playbook.
- Say goodbye to the user."""
        ast = markdown_to_ast(markdown)
        expected = {
            "type": "h1",
            "text": "HelloWorld Agent",
            "children": [
                {
                    "type": "paragraph",
                    "text": "This is a simple Hello World agent.",
                    "markdown": "This is a simple Hello World agent.",
                },
                {
                    "type": "h2",
                    "text": "HelloWorld",
                    "children": [
                        {
                            "type": "h3",
                            "text": "Trigger",
                            "children": [
                                {
                                    "type": "paragraph",
                                    "text": "When the user starts a conversation or asks for a greeting.",
                                    "markdown": "When the user starts a conversation or asks for a greeting.",
                                }
                            ],
                            "markdown": "### Trigger\nWhen the user starts a conversation or asks for a greeting.",
                        },
                        {
                            "type": "h3",
                            "text": "Steps",
                            "children": [
                                {
                                    "type": "list",
                                    "children": [
                                        {
                                            "type": "list-item",
                                            "text": 'Greet the user with a friendly "Hello, World!" message.',
                                            "markdown": '- Greet the user with a friendly "Hello, World!" message.',
                                        },
                                        {
                                            "type": "list-item",
                                            "text": "Explain that this is a demonstration of a simple Hello World playbook.",
                                            "markdown": "- Explain that this is a demonstration of a simple Hello World playbook.",
                                        },
                                        {
                                            "type": "list-item",
                                            "text": "Say goodbye to the user.",
                                            "markdown": "- Say goodbye to the user.",
                                        },
                                    ],
                                    "markdown": '- Greet the user with a friendly "Hello, World!" message.\n- Explain that this is a demonstration of a simple Hello World playbook.\n- Say goodbye to the user.',
                                }
                            ],
                            "markdown": '### Steps\n- Greet the user with a friendly "Hello, World!" message.\n- Explain that this is a demonstration of a simple Hello World playbook.\n- Say goodbye to the user.',
                        },
                    ],
                    "markdown": '## HelloWorld\n### Trigger\nWhen the user starts a conversation or asks for a greeting.\n### Steps\n- Greet the user with a friendly "Hello, World!" message.\n- Explain that this is a demonstration of a simple Hello World playbook.\n- Say goodbye to the user.',
                },
            ],
            "markdown": '# HelloWorld Agent\nThis is a simple Hello World agent.\n## HelloWorld\n### Trigger\nWhen the user starts a conversation or asks for a greeting.\n### Steps\n- Greet the user with a friendly "Hello, World!" message.\n- Explain that this is a demonstration of a simple Hello World playbook.\n- Say goodbye to the user.',
        }
        self.assertEqual(ast, expected)


if __name__ == "__main__":
    unittest.main()
