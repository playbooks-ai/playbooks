# CLI Utilities Examples - Complete Guide

This guide provides detailed examples and explanations for building command-line utilities with Playbooks.

## Table of Contents

1. [Basic CLI Utilities](#basic-cli-utilities)
2. [MCP Agents in CLI Utilities](#mcp-agents-in-cli-utilities)
3. [In-Process MCP Servers with Memory Transport](#in-process-mcp-servers-with-memory-transport)
4. [Advanced Examples](#advanced-examples)

## Basic CLI Utilities

### Hello CLI (`hello_cli.pb`)

A simple greeting generator that demonstrates CLI parameter handling.

```markdown
## Main($name)
cli_entry: true

### Triggers
- At the beginning
### Steps
- Generate a personalized greeting for $name
- Say(user, greeting)
- End program
```

**Usage:**
```bash
playbooks run hello_cli.pb --name "Alice"
playbooks run hello_cli.pb --name "Bob" --message "Make it formal"
```

### Text Summarizer (`summarize_text.pb`)

Demonstrates stdin handling for Unix-style piping.

**Usage:**
```bash
cat article.txt | playbooks run summarize_text.pb
echo "Long text here..." | playbooks run summarize_text.pb --message "Focus on main points"
```

## MCP Agents in CLI Utilities

Playbooks can integrate with MCP (Model Context Protocol) servers to provide external tools and capabilities to your CLI utilities.

### Traditional MCP Setup (External Servers)

Previously, you needed to run MCP servers separately:

```bash
# Terminal 1: Start filesystem server
python examples/deepagents/filesystem_mcp.py

# Terminal 2: Start shell server
python examples/deepagents/shell_mcp.py

# Terminal 3: Run your playbook
playbooks run generate_release_notes.pb --start HEAD~10 --end HEAD
```

**Playbook configuration:**
```yaml
# FilesystemAgent
remote:
  type: mcp
  transport: streamable-http
  url: http://127.0.0.1:8000/mcp

---

# ShellAgent
remote:
  type: mcp
  transport: streamable-http
  url: http://127.0.0.1:8002/mcp
```

## In-Process MCP Servers with Memory Transport

Memory transport allows you to run MCP servers in-process, eliminating the need for separate server processes. This is perfect for CLI utilities!

### Benefits

✓ **No separate processes** - Servers load automatically when needed  
✓ **Simpler deployment** - Just one command to run  
✓ **Faster startup** - No network overhead  
✓ **Easier debugging** - Everything in one process  
✓ **Automatic caching** - Server loaded once per session  

### URL Format

Memory transport uses a special URL scheme:

```
memory://path/to/server.py              # Default: looks for 'mcp' variable
memory://path/to/server.py?var=server   # Custom variable name
memory:///absolute/path/to/server.py    # Absolute path (3 slashes)
```

### Basic Example

**MCP Server File (`my_server.py`):**
```python
from fastmcp import FastMCP

mcp = FastMCP("MyServer")

@mcp.tool()
def greet(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"

@mcp.tool()
def calculate(a: int, b: int, operation: str) -> int:
    """Perform calculation."""
    if operation == "add":
        return a + b
    elif operation == "multiply":
        return a * b
    return 0
```

**Playbook (`calculator.pb`):**
```markdown
# CalculatorAgent
metadata:
  remote:
    type: mcp
    transport: memory
    url: memory://./my_server.py
---
Agent providing calculation tools.

## Main($a, $b, $operation)
cli_entry: true

### Triggers
- At the beginning
### Steps
- Use CalculatorAgent to calculate $a $operation $b
- Say(user, result)
- End program
```

**Usage:**
```bash
playbooks run calculator.pb --a 5 --b 3 --operation add
# Output: 8
```

### Path Resolution

Memory transport resolves paths relative to **the playbook file's directory** (not the current working directory). This makes playbooks portable and paths intuitive:

```yaml
# Relative to the .pb file's location
url: memory://./my_server.py             # Same directory as playbook
url: memory://../deepagents/server.py    # Parent directory
url: memory://tools/custom.py            # Subdirectory

# Absolute path (note 3 slashes)
url: memory:///absolute/path/to/server.py
```

**Example**: If your playbook is at `/project/examples/my_app.pb` and you use `url: memory://../tools/server.py`, it will resolve to `/project/tools/server.py`.

### Custom Variable Names

If your MCP server uses a different variable name:

```python
# server.py
from fastmcp import FastMCP

my_custom_server = FastMCP("Server")  # Not named 'mcp'

@my_custom_server.tool()
def custom_tool() -> str:
    return "works!"
```

**Specify the variable name in the URL:**
```yaml
remote:
  type: mcp
  transport: memory
  url: memory://./server.py?var=my_custom_server
```

### Real-World Example: Release Notes Generator

The `generate_release_notes.pb` example uses memory transport to access filesystem and shell tools:

```markdown
# ReleaseNotesGenerator
Generates release notes by analyzing git commits between two points

## Main($start, $end)
cli_entry: true

### Triggers
- At the beginning
### Steps
- Use shell command "git log --notes $start..$end" to get $commit_logs
- Analyze commits and categorize by type (Added, Fixed, etc.)
- Format as professional release notes
- Say(user, $release_notes)
- End program

---

# FilesystemAgent
Agent providing file system operations through MCP integration.

remote:
  type: mcp
  transport: memory
  url: memory://../deepagents/filesystem_mcp.py

---

# ShellAgent
Agent providing shell command execution through MCP integration.

remote:
  type: mcp
  transport: memory
  url: memory://../deepagents/shell_mcp.py
```

**Usage:**
```bash
# Generate release notes from last 10 commits
playbooks run generate_release_notes.pb --start HEAD~10 --end HEAD

# Between two tags
playbooks run generate_release_notes.pb --start v0.6.0 --end v0.7.0

# With custom instructions
playbooks run generate_release_notes.pb \
  --start HEAD~20 \
  --end HEAD \
  --message "Focus on user-facing changes"
```

## Advanced Examples

### Multiple In-Process Servers

You can use multiple memory transport agents in the same playbook:

```markdown
## Main($task)
cli_entry: true

### Steps
- Use FilesystemAgent to read configuration
- Use DatabaseAgent to query data
- Use WebAgent to fetch additional info
- Combine and process results
- Say(user, output)
- End program

---

# FilesystemAgent
remote:
  type: mcp
  transport: memory
  url: memory://./tools/filesystem.py

---

# DatabaseAgent
remote:
  type: mcp
  transport: memory
  url: memory://./tools/database.py

---

# WebAgent
remote:
  type: mcp
  transport: memory
  url: memory://./tools/web.py
```

### Combining Local and Remote Agents

Mix in-process and remote MCP servers:

```markdown
# LocalFileSystem
remote:
  type: mcp
  transport: memory
  url: memory://./local_fs.py

---

# RemoteAPI
remote:
  type: mcp
  transport: streamable-http
  url: https://api.example.com/mcp
```

### Creating Reusable MCP Servers

Build reusable MCP server libraries:

**File: `tools/common_tools.py`**
```python
from fastmcp import FastMCP

mcp = FastMCP("CommonTools")

@mcp.tool()
def read_json(path: str) -> dict:
    """Read and parse JSON file."""
    import json
    with open(path) as f:
        return json.load(f)

@mcp.tool()
def write_json(path: str, data: dict) -> str:
    """Write JSON to file."""
    import json
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    return f"Written to {path}"

@mcp.tool()
def list_directory(path: str) -> list:
    """List directory contents."""
    import os
    return os.listdir(path)
```

Use in any playbook:
```yaml
# ToolsAgent
remote:
  type: mcp
  transport: memory
  url: memory://./tools/common_tools.py
```

## Troubleshooting

### Common Errors

**Error: "MCP server file not found"**
- Check that the path is correct relative to your current working directory
- Use absolute paths if needed: `memory:///absolute/path/to/server.py`

**Error: "Module does not contain variable 'mcp'"**
- Your server file needs a FastMCP instance assigned to a variable
- Use `?var=your_variable_name` if it's not named `mcp`

**Error: "Failed to execute module"**
- Check for syntax errors in your MCP server file
- Ensure all imports are available in your environment

### Debugging Tips

1. **Test your MCP server independently:**
```bash
python -c "from my_server import mcp; print(mcp)"
```

2. **Use absolute paths during development:**
```yaml
url: memory:///full/path/to/server.py
```

3. **Enable verbose logging:**
```bash
playbooks run script.pb --verbose
```

4. **Check working directory:**
```bash
pwd  # See where you are
playbooks run script.pb --args
```

## Best Practices

1. **Keep MCP servers focused** - One server per domain (filesystem, shell, database, etc.)

2. **Use descriptive agent names** - Makes playbook logic clearer

3. **Add docstrings to tools** - They become part of the tool description:
```python
@mcp.tool()
def process_data(input: str) -> str:
    """Process input data and return formatted result.
    
    Args:
        input: Raw data string to process
        
    Returns:
        Formatted and processed string
    """
    return input.upper()
```

4. **Organize tools by functionality** - Group related tools in the same server

5. **Version your MCP servers** - Track changes to tool interfaces

6. **Test MCP servers independently** - Unit test your tools before using in playbooks

## Performance Notes

- **Caching**: MCP servers are loaded once and cached for the entire session
- **Startup**: First load includes import time, subsequent uses are instant
- **Memory**: All servers stay in memory until program exits
- **Isolation**: Each server runs in the same process but maintains separate state

## Next Steps

- Explore existing MCP servers in `examples/deepagents/`
- Create your own MCP tools for common tasks
- Build CLI utilities that combine multiple capabilities
- Share your MCP servers as reusable libraries

## See Also

- [MCP Documentation](../../docs/guides/mcp-integration.md)
- [CLI Utility Guide](README.md)
- [Example MCP Servers](../deepagents/)

