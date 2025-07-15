<div align="center">
   <h1>
   <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://playbooks-ai.github.io/playbooks-docs/assets/images/playbooks-logo-dark.png">
      <img alt="Text changing depending on mode. Light: 'So light!' Dark: 'So dark!'" src="https://playbooks-ai.github.io/playbooks-docs/assets/images/playbooks-logo.png" width=200 height=200>
   </picture>
  <h2 align="center">Create AI agents with natural language programs</h2>
</div>

<div align="center">

[![GitHub License](https://img.shields.io/github/license/playbooks-ai/playbooks?logo=github)](https://github.com/playbooks-ai/playbooks/blob/master/LICENSE)
[![PyPI Version](https://img.shields.io/pypi/v/playbooks?logo=pypi&color=blue)](https://pypi.org/project/playbooks/)
[![Python Version](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://www.python.org/)
[![Documentation](https://img.shields.io/badge/Docs-GitHub-blue?logo=github)](https://playbooks-ai.github.io/playbooks-docs/)
[![Test](https://github.com/playbooks-ai/playbooks/actions/workflows/test.yml/badge.svg)](https://github.com/playbooks-ai/playbooks/actions/workflows/test.yml)
[![Lint](https://github.com/playbooks-ai/playbooks/actions/workflows/lint.yml/badge.svg)](https://github.com/playbooks-ai/playbooks/actions/workflows/lint.yml)
[![GitHub issues](https://img.shields.io/github/issues/playbooks-ai/playbooks)](https://github.com/playbooks-ai/playbooks/issues)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-green.svg)](https://github.com/playbooks-ai/playbooks/blob/master/CONTRIBUTING.md)
[![Contributors](https://img.shields.io/github/contributors/playbooks-ai/playbooks)](https://github.com/playbooks-ai/playbooks/graphs/contributors)

[![Homepage](https://img.shields.io/badge/Homepage-runplaybooks.ai-red?logo=google-chrome)](https://runplaybooks.ai/)
</div>

Playbooks is an innovative Python framework for building and executing AI agents using "playbooks" – structured workflows defined in natural language (via Markdown-based .pb files) or Python code. Created by Amol Kelkar, the framework is part of the world's first Software 3.0 tech stack Playbooks AI. 

Playbooks compiles markdown-based .pb files into an intermediate "assembly" format (.pbasm), enabling efficient runtime execution. The framework supports local, remote, and multi-agent scenarios, with features like event-driven triggers, shared variables/artifacts, and seamless integration between natural language steps and Python functions on a unified call stack. It's designed for scalability, observability, and accessibility, making AI agent development available to non-programmers while offering depth for experts and Enterprise use cases.

## Novelty and Innovation

Playbooks stands out in the AI agent landscape (e.g., compared to LangChain or AutoGPT) by evolving programming toward Software 3.0, where natural language becomes a first-class programming language:

- **Natural Language Programming**: Write workflows in plain English (e.g., "If the user asks a question, search for facts and respond"). The compiler performs **semantic static analysis** – a novel feature that infers intent, adds annotations (e.g., QUE for queueing playbook calls, CND for conditions), variables/types, line numbers, and writes missing descriptions, data types.

- **Compiler-Driven Reliability**: Unlike raw prompt chaining, Playbooks compiles .pb to .pbasm, enriching it for reliable execution. This intermediate representation reduces LLM hallucinations by providing structured guidance, enabling static checks (e.g., type inference, loop detection) on natural language – unprecedented in LLM frameworks.

- **LLM as CPU with Hybrid Stack**: The runtime treats LLMs as processors in a fetch-decode-execute loop, but with a twist: Markdown (natural language) steps run via LLM interpretation, while Python code executes via Python interpreter – all on the **same call stack**. This hybrid model allows fluid interop (e.g., an English step yields to Python for computation, and Python code calls Markdown playbooks).

- **PlaybooksLM**: A specialized small LLM, fine-tuned for playbook execution. It addresses general LLM drawbacks like non-determinism, high costs, and latency, ensuring fast, accurate runs for deep workflows.

- **Multi-Agent and Remote Execution**: Built-in communication and MCP (Model Context Protocol) for distributed agents, with transports like WebSocket or SSE. Triggers enable reactive program composition, even across agents.

- **Advanced Capabilities**: Playbooks enables completely novel paradigms. Here are a few examples - Dynamic generation, compilation, and execution of playbooks at runtime (e.g., via LLM-generated .pb files based on reasoning and planning); Runtime discovery of agents and playbooks enables dynamic program composability (e.g., agents querying and integrating others' public and exported playbooks on-the-fly); Triggers can automatically add and execute verifiability constraints like pre-conditions and post-conditions, ensuring robust, self-validating workflows; Intelligent program deviation when unexpected conditions arise.

This positions Playbooks as a step toward AGI-friendly programming: Compile-time intelligence + runtime efficiency + dynamic program synthesis and program search.

## Use Cases

Playbooks excels in scenarios requiring structured, adaptive AI workflows. Here are detailed examples:

- **Conversational Agents/Chatbots**: Define multi-turn dialogues in natural language. E.g., a travel advisor: "Ask for destination preferences, search facts, recommend itineraries." Use triggers for reactive responses; hybrid with Python for API calls (e.g., weather data).
  
- **Automation and Task Orchestration**: Script workflows like data extraction: "Read file, parse content, save artifacts." Ideal for ETL pipelines or order processing, with conditions for error handling.

- **Multi-Agent Systems**: Simulate customer support teams (router agent + specialists) or research simulations (data gatherer + analyzer).

- **ReAct-Style Reasoning**: Adaptive problem-solving: "Observe, think, act" loops in English, with LLM deciding next steps. Applications: Game AI, troubleshooting bots.

- **Prototyping and Education**: Business users can easily create AI agents with English logic.

## Quickstart

Requires Python 3.12+:

### Installation

```bash
pip install playbooks
```

## Sep up environment

```bash
cp .env.example .env
```

Edit `.env` to specify `ANTHROPIC_API_KEY`.


### Your first playbooks program

Create a file named `hello.pb` with the following content:

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

### Run hello.pb

```bash
playbooks run hello.pb
```

### Programmatic
   ```python
   from playbooks import Playbooks

   pb = Playbooks(["hello.pb"])
   await pb.initialize()
   await pb.program.run_till_exit()
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
