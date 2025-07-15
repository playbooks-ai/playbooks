# Example MCP Server
remote:
  type: mcp
  url: memory://test
  transport: memory


# Example MCP Client Agent

## Main

### Triggers
- When program starts

### Steps
- get secret from Example MCP Server
- reveal secret to user
- end program