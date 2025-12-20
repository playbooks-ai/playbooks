# Example MCP Server
remote:
  type: mcp
  url: memory://./test_mcp.py
  transport: memory


# Example MCP Client Agent

## Main

### Triggers
- When program starts

### Steps
- get secret from Example MCP Server
- reveal secret to user
- end program