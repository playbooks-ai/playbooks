<div align="center">
   <h1>
   <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://playbooks-ai.github.io/playbooks-docs/assets/images/playbooks-logo-dark.png">
      <img alt="Text changing depending on mode. Light: 'So light!' Dark: 'So dark!'" src="https://playbooks-ai.github.io/playbooks-docs/assets/images/playbooks-logo.png" width=200 height=200>
   </picture>
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
- **Execution Observability** - Full audit trail of every step of execution and explainability for every decision made by the AI agent


## 🏁 Quick Start

### Installation

```bash
pip install playbooks
```

### Create Your First Playbook

Create a file named `hello.pb`:

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
python -m playbooks.applications.agent_chat hello.pb --verbose
```

### VSCode Support (Optional)

Install the **Playbooks Language Support** extension for Visual Studio Code:

1. Open VSCode
2. Go to Extensions (Ctrl+Shift+X / Cmd+Shift+X)
3. Search for "Playbooks Language Support"
4. Click Install

The extension provides debugging capabilities for playbooks programs, making it easier to develop and troubleshoot your AI agents. Once the plugin is installed, you can open a playbooks .pb file and start debugging!

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
