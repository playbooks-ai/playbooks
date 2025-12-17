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
- Call ExampleMCPServer.get_secret() to get the secret
- reveal secret to user
- end program