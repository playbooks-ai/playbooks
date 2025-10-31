# Deep Thinker agent example

## Setup

```bash
python --version # should be 3.12+
export ANTHROPIC_API_KEY=sk-ant-api03-... # get your API key from https://console.anthropic.com/

pip install -r requirements.txt
```

## Running the MCP server

```bash
fastmcp run mcp.py -t streamable-http --port 8000
```

## Running the Playbooks agent

```bash
playbooks run deep_thinker.pb
```