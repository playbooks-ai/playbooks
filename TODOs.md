# TODOs

## Core runtime
- [x] Artifacts (create python/md, list python/md, load python/md)
- [ ] Auto-load referenced/returned artifacts
- [ ] Artifact management playbooks?
- [ ] Add more trigger types
- [ ] inline playbooks (leaf playbooks that should be executed by the LLM without yielding)
- [ ] Investigate join calculus for additional control flow annotations in intermediate format

## Application infrastructure
- [ ] playbooks hello.pb --application agent_chat --verbose
- [ ] Steaming!
- [ ] Websockets
- [ ] Can we use SSE?
- [ ] Telemetry

## Website
- [ ] Website

## Agent
- [ ] Per agent LLM config
- [ ] Run agent as MCP server
- [ ] Cross-agent triggers
- [ ] Cross-agent explicit calls, implicit calls
- [ ] Use tools from MCP servers
- [ ] Running a public playbook from an MCP server
- [ ] Register remote agent using URL (as MCP server?)
- [ ] Public playbooks - mark playbooks as public and call public playbooks
- [ ] Exported playbooks - mark playbooks for export and import their implementations

## Memory
- [ ] Memory

## Demo applications
- [ ] Demonstrate amazing RAG results with an advanced RAG playbook

## PlaybooksLM / LLM useage
- [ ] PlaybooksLM
- [ ] Which LLM should execute each line? Maybe PlaybooksLM acts as a router, e.g. for TNK lines it invokes the LLM configured for deep thinking.
