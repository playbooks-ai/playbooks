<div align="center">
  <h1 align="center">Playbooks AI</h1>
  <h2 align="center">Create AI agents with natural language programs</h2>
</div>

<div align="center">
   <a href="https://pypi.org/project/playbooks/">
      <img src="https://img.shields.io/pypi/v/playbooks?logo=pypi&style=plastic&color=blue" alt="PyPI Version"/></a>
   <a href="https://www.python.org/">
      <img src="https://img.shields.io/badge/Python-3.10-blue?style=plastic&logo=python" alt="Python Version"></a>
   <a href="https://github.com/playbooks-ai/playbooks/blob/master/LICENSE">
      <img src="https://img.shields.io/github/license/playbooks-ai/playbooks?logo=github&style=plastic&color=green" alt="GitHub License"></a>   
   <a href="https://playbooks-ai.github.io/playbooks-docs/">
      <img src="https://img.shields.io/badge/Docs-GitHub-blue?logo=github&style=plastic&color=green" alt="Documentation"></a>
   <br>
   <a href="https://github.com/playbooks-ai/playbooks/actions/workflows/test.yml">
      <img src="https://github.com/playbooks-ai/playbooks/actions/workflows/test.yml/badge.svg", alt="Test"></a>
   <a href="https://github.com/playbooks-ai/playbooks/actions/workflows/lint.yml">
      <img src="https://github.com/playbooks-ai/playbooks/actions/workflows/lint.yml/badge.svg", alt="Lint"></a>
   <!-- <a href="https://runplaybooks.ai/">
      <img src="https://img.shields.io/badge/Homepage-runplaybooks.ai-red?style=plastic&logo=google-chrome" alt="Homepage"></a> -->
</div>

**Playbooks AI** is a powerful framework for building AI agents with Natural Language Programming. It introduces a new "english-like", semantically interpreted programming language with reliable, auditable execution.

>Playbooks AI is still in early development. We're working hard and would love your feedback and contributions.

Playbooks AI goes well beyond LLM tool calling. You can fluidly combine: 

- Business processes written as natural language playbooks
- Python code for external system integrations, algorithmic logic, and complex data processing
- Multiple local and remote AI agents interacting in novel ways

Unlike standard LLM prompts that offer no execution guarantees, Playbooks provides full visibility into every step of execution, ensuring your AI system follows all rules, executes steps in the correct order, and completes all required actions. Track and verify the entire execution path with detailed state tracking, call stacks, and execution logs.

## 🚀 Key Features
- **Natural Language Programming** - Write agent logic in plain English with markdown playbooks that look like a step-by-step recipe
- **Python Integration** - Seamlessly call natural language and Python playbooks on the same call stack for a radically new programming paradigm
- **Multi-Agent Architecture** - Build systems with multiple specialized agents, interact and leverage external AI agents
- **Event-Driven Programming** - Use triggers to create reactive, context-aware agents
- **Variables, Artifacts and Memory** - Native support for managing agent state using variables, artifacts and memory
- **Execution Observability** - Full audit trail of every step of execution and explainability for every decision made the the AI agent


## 🏁 Quick Start

### Installation

```bash
pip install playbooks
```

### Create Your First Playbook

Create a file named `hello.md`:

```markdown
# Personalized greeting
This program greets the user by name

## Greet
### Triggers
- At the beginning of the program
### Steps
- Ask the user for their name
- Say hello to the user by name and welcome them to Playbooks AI
- End program
```

### Run Your Playbook

```bash
python -m playbooks.applications.agent_chat hello.md --verbose
```

## 📚 Documentation

Visit our [documentation](https://playbooks-ai.github.io/playbooks-docs/) for comprehensive guides, tutorials, and reference materials.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributors

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->
<!-- ALL-CONTRIBUTORS-LIST:END -->
<a href="https://github.com/playbooks-ai/playbooks/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=playbooks-ai/playbooks" />
</a>
