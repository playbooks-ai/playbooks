# DeepAgent Playbooks - Files Reference

Quick reference for all files in this implementation.

## Core Files

### deepagent.pb (142 lines)
**Main Playbooks program** - Defines all agents and their workflows

- **CodingAgent**: Main orchestrator for coding tasks
- **ResearchAgent**: Specialized subagent for deep research
- **FilesystemAgent**: Remote MCP agent for file operations
- **WebAgent**: Remote MCP agent for web tools
- **ShellAgent**: Remote MCP agent for shell commands

**Usage**: `playbooks run deepagent.pb`

---

## MCP Servers

### filesystem_mcp.py (~350 lines)
**File system operations server** - Port 8000

**Tools**:
- `ls(path)` - List directory contents
- `read_file(file_path, offset, limit)` - Read files with pagination
- `write_file(file_path, content)` - Create new files
- `edit_file(file_path, old_string, new_string, replace_all)` - Edit files
- `glob(pattern, path)` - Find files by pattern
- `grep(pattern, path, glob_pattern, output_mode)` - Search file contents

**Start**: `fastmcp run filesystem_mcp.py -t streamable-http --port 8000`

### web_tools_mcp.py (~150 lines)
**Web research tools server** - Port 8001

**Tools**:
- `web_search(query, max_results, topic, include_raw_content)` - Tavily search
- `fetch_url(url, timeout)` - Fetch and convert HTML to markdown
- `http_request(url, method, headers, data, params, timeout)` - HTTP requests

**Start**: `fastmcp run web_tools_mcp.py -t streamable-http --port 8001`

### shell_mcp.py (~80 lines)
**Shell execution server** - Port 8002

**Tools**:
- `shell(command, working_dir, timeout)` - Execute shell commands
- `get_cwd()` - Get current working directory

**Start**: `fastmcp run shell_mcp.py -t streamable-http --port 8002`

---

## Configuration Files

### requirements.txt
Python dependencies for the project:
- `playbooks` - Playbooks AI framework
- `fastmcp` - MCP server framework
- `requests` - HTTP library
- `markdownify` - HTML to markdown conversion
- `tavily-python` - Web search
- `rich` - Terminal UI (optional)

**Install**: `pip install -r requirements.txt`

### playbooks.toml
Playbooks configuration file with settings for:
- Caching
- Model configuration
- Logging
- Human-in-the-loop approvals
- MCP endpoints

---

## Helper Scripts

### start_servers.sh
**Bash script to start all MCP servers**

Features:
- Starts all three MCP servers
- Uses tmux for multiplexing (or background processes)
- Checks for dependencies
- Provides status and instructions

**Usage**: `./start_servers.sh`

### stop_servers.sh
**Bash script to stop all MCP servers**

Features:
- Stops tmux session or background processes
- Cleans up PID files
- Provides manual fallback instructions

**Usage**: `./stop_servers.sh`

---

## Documentation Files

### README.md
**Comprehensive documentation** covering:
- Architecture overview
- Installation instructions
- Usage examples
- Feature descriptions
- Comparison to original DeepAgents
- Extensibility guide
- Troubleshooting tips

**Read first** for full understanding of the system.

### QUICKSTART.md
**5-minute getting started guide**:
- Quick setup steps
- First interaction examples
- Common commands
- Troubleshooting basics

**Read this** to get up and running immediately.

### MIGRATION.md
**Detailed comparison with original DeepAgents**:
- Side-by-side code comparisons
- Architecture mapping
- Design decision rationale
- Code size statistics (77% reduction)
- When to use which approach

**Read this** to understand the conversion and benefits.

### OVERVIEW.md
**High-level implementation overview**:
- Project structure
- Architecture explanation
- Key features
- Design principles
- Usage patterns
- Extensibility guide

**Read this** for architectural understanding.

### FILES.md (this file)
Quick reference for all files in the project.

---

## File Tree

```
playbooks/
├── deepagent.pb              # Main Playbooks program (142 lines)
│
├── filesystem_mcp.py         # Filesystem MCP server (~350 lines)
├── web_tools_mcp.py         # Web tools MCP server (~150 lines)
├── shell_mcp.py             # Shell MCP server (~80 lines)
│
├── requirements.txt         # Python dependencies
├── playbooks.toml          # Playbooks configuration
│
├── start_servers.sh        # Start all MCP servers (executable)
├── stop_servers.sh         # Stop all MCP servers (executable)
│
├── README.md               # Comprehensive documentation
├── QUICKSTART.md           # 5-minute quick start guide
├── MIGRATION.md            # Comparison with DeepAgents
├── OVERVIEW.md             # Architecture overview
└── FILES.md                # This file
```

---

## Quick Commands Reference

```bash
# Setup
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
export TAVILY_API_KEY=tvly-...  # optional

# Start servers
./start_servers.sh

# Run agent
playbooks run deepagent.pb

# Playground mode
playbooks playground deepagent.pb

# Stop servers
./stop_servers.sh

# Manual server start (in separate terminals)
fastmcp run filesystem_mcp.py -t streamable-http --port 8000
fastmcp run web_tools_mcp.py -t streamable-http --port 8001
fastmcp run shell_mcp.py -t streamable-http --port 8002
```

---

## Development Files

When extending the system, you'll primarily work with:

1. **deepagent.pb** - Modify agent behavior and workflows
2. **{filesystem,web_tools,shell}_mcp.py** - Add new tools
3. **playbooks.toml** - Adjust configuration

Test files (create as needed):
- `test_filesystem.py` - Unit tests for filesystem tools
- `test_web_tools.py` - Unit tests for web tools
- `test_agent.py` - Integration tests for agent behavior

Runtime files (auto-generated):
- `.mcp_servers.pid` - Process IDs when running in background
- `filesystem_mcp.log` - Filesystem server logs
- `web_tools_mcp.log` - Web tools server logs
- `shell_mcp.log` - Shell server logs

---

## Total Lines of Code

| Category | Lines |
|----------|-------|
| **Playbooks Program** | 142 |
| **MCP Servers** | ~580 |
| **Documentation** | ~2,000 |
| **Scripts** | ~150 |
| **TOTAL CODE** | **~870** |

Compare to original DeepAgents: **~3,300 lines** (77% reduction)

---

## Next Steps

1. **First time?** → Read [QUICKSTART.md](QUICKSTART.md)
2. **Want details?** → Read [README.md](README.md)
3. **Understand design?** → Read [OVERVIEW.md](OVERVIEW.md)
4. **Compare approaches?** → Read [MIGRATION.md](MIGRATION.md)
5. **Quick reference?** → This file (FILES.md)

---

## License

Same as DeepAgents - see main LICENSE file in repository root.

---

## Credits

Based on [DeepAgents](https://github.com/langchain-ai/deepagents) by LangChain, inspired by Claude Code (Anthropic).

Converted to Playbooks AI to demonstrate natural language agent programming with MCP integration.

