#!/bin/bash

# Script to stop all MCP servers

echo "Stopping DeepAgent MCP Servers..."
echo

# Try to kill tmux session first
if command -v tmux &> /dev/null; then
    if tmux has-session -t deepagent-mcp 2>/dev/null; then
        tmux kill-session -t deepagent-mcp
        echo "✓ Stopped tmux session 'deepagent-mcp'"
        exit 0
    fi
fi

# Fallback: Kill background processes
if [ -f .mcp_servers.pid ]; then
    while read pid; do
        if ps -p $pid > /dev/null 2>&1; then
            kill $pid
            echo "✓ Stopped process $pid"
        fi
    done < .mcp_servers.pid
    rm .mcp_servers.pid
    echo
    echo "✓ All MCP servers stopped"
else
    echo "No PID file found. Servers may not be running."
    echo
    echo "To manually stop servers, find and kill processes on ports 8000-8002:"
    echo "  lsof -ti:8000 | xargs kill"
    echo "  lsof -ti:8001 | xargs kill"
    echo "  lsof -ti:8002 | xargs kill"
fi

