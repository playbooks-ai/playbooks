# Example MCP Server
remote:
  type: mcp
  transport: http
  url: http://localhost:8088/mcp


# Example MCP Client Agent

## Main

### Triggers
- When program starts

### Steps
- get secret from Example MCP Server
- reveal secret to user
- end program