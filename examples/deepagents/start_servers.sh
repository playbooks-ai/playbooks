#!/bin/bash

# Script to start all MCP servers for DeepAgent Playbooks

echo "Starting DeepAgent MCP Servers..."
echo

# Check if fastmcp is installed
if ! command -v fastmcp &> /dev/null; then
    echo "Error: fastmcp not found. Please install it:"
    echo "  pip install fastmcp"
    exit 1
fi

# Check if playbooks is installed
if ! command -v playbooks &> /dev/null; then
    echo "Warning: playbooks not found. Install it to run the agent:"
    echo "  pip install playbooks"
    echo
fi

# Check for API keys
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Warning: ANTHROPIC_API_KEY not set"
    echo "  export ANTHROPIC_API_KEY=sk-ant-..."
    echo
fi

# Create a tmux session with three panes
if command -v tmux &> /dev/null; then
    echo "Starting MCP servers in tmux session 'deepagent-mcp'..."
    echo
    
    # Create new tmux session
    tmux new-session -d -s deepagent-mcp
    
    # Split into three panes
    tmux split-window -h -t deepagent-mcp
    tmux split-window -v -t deepagent-mcp
    tmux select-pane -t 0
    tmux split-window -v -t deepagent-mcp
    
    # Start servers in each pane
    tmux send-keys -t deepagent-mcp:0.0 'echo "Starting Filesystem MCP (port 8000)..." && fastmcp run filesystem_mcp.py -t streamable-http --port 8000' C-m
    tmux send-keys -t deepagent-mcp:0.1 'echo "Starting Web Tools MCP (port 8001)..." && fastmcp run web_tools_mcp.py -t streamable-http --port 8001' C-m
    tmux send-keys -t deepagent-mcp:0.2 'echo "Starting Shell MCP (port 8002)..." && fastmcp run shell_mcp.py -t streamable-http --port 8002' C-m
    
    echo "✓ MCP servers started in tmux session 'deepagent-mcp'"
    echo
    echo "To view servers:"
    echo "  tmux attach -t deepagent-mcp"
    echo
    echo "To stop servers:"
    echo "  tmux kill-session -t deepagent-mcp"
    echo
    echo "Once servers are running, start the agent:"
    echo "  playbooks run deepagent.pb"
    
else
    # Fallback: Start in background processes
    echo "tmux not found. Starting servers in background..."
    echo
    
    echo "Starting Filesystem MCP (port 8000)..."
    fastmcp run filesystem_mcp.py -t streamable-http --port 8000 > filesystem_mcp.log 2>&1 &
    FILESYSTEM_PID=$!
    
    echo "Starting Web Tools MCP (port 8001)..."
    fastmcp run web_tools_mcp.py -t streamable-http --port 8001 > web_tools_mcp.log 2>&1 &
    WEBTOOLS_PID=$!
    
    echo "Starting Shell MCP (port 8002)..."
    fastmcp run shell_mcp.py -t streamable-http --port 8002 > shell_mcp.log 2>&1 &
    SHELL_PID=$!
    
    # Save PIDs to file for stop script
    echo "$FILESYSTEM_PID" > .mcp_servers.pid
    echo "$WEBTOOLS_PID" >> .mcp_servers.pid
    echo "$SHELL_PID" >> .mcp_servers.pid
    
    echo
    echo "✓ MCP servers started in background"
    echo "  Filesystem MCP: PID $FILESYSTEM_PID (port 8000)"
    echo "  Web Tools MCP:  PID $WEBTOOLS_PID (port 8001)"
    echo "  Shell MCP:      PID $SHELL_PID (port 8002)"
    echo
    echo "Logs are being written to:"
    echo "  filesystem_mcp.log"
    echo "  web_tools_mcp.log"
    echo "  shell_mcp.log"
    echo
    echo "To stop servers, run:"
    echo "  ./stop_servers.sh"
    echo
    echo "Once servers are running, start the agent:"
    echo "  playbooks run deepagent.pb"
fi

