# Stock Analysis with Playbooks

**Python 3.12+ is required**
**Required: Anthropic API key ANTHROPIC_API_KEY in environment**
**Required: Serper Dev API key SERPER_API_KEY in environment**

1. Install playbooks

```
pip install playbooks
```

2. Run the MCP servers for file system and web search in two separate terminals

```
python file_system_mcp.py
python web_mcp.py
```

3. Run the stock analysis playbook in another terminal

```
python run.py
```

4. The stock analysis report will be saved in the `output` folder.