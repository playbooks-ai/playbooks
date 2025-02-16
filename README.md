<div align="center">
  <h1 align="center">Playbooks AI</h1>
</div>

<div align="center">
   <a href="https://pypi.org/project/playbooks/">
      <img src="https://img.shields.io/pypi/v/playbooks?logo=pypi&style=plastic&color=blue" alt="PyPI Version"/></a>
   <a href="https://www.python.org/">
      <img src="https://img.shields.io/badge/Python-3.10-blue?style=plastic&logo=python" alt="Python Version"></a>
   <a href="https://github.com/playbooks-ai/playbooks/blob/master/LICENSE">
      <img src="https://img.shields.io/github/license/playbooks-ai/playbooks?logo=github&style=plastic&color=green" alt="GitHub License"></a>   
   <a href="https://github.com/playbooks-ai/playbooks/tree/master/docs">
      <img src="https://img.shields.io/badge/Docs-GitHub-blue?logo=github&style=plastic&color=red" alt="Documentation"></a>
   <br>
   <a href="https://github.com/playbooks-ai/playbooks/actions/workflows/test.yml">
      <img src="https://github.com/playbooks-ai/playbooks/actions/workflows/test.yml/badge.svg", alt="Test"></a>
   <a href="https://github.com/playbooks-ai/playbooks/actions/workflows/lint.yml">
      <img src="https://github.com/playbooks-ai/playbooks/actions/workflows/lint.yml/badge.svg", alt="Lint"></a>
   <a href="https://runplaybooks.ai/">
      <img src="https://img.shields.io/badge/Homepage-runplaybooks.ai-green?style=plastic&logo=google-chrome" alt="Homepage"></a>
</div>

<div align="center">
  <h2 align="center">Train AI Agents with Human Readable Playbooks</h2>
</div>

Playbooks AI™ is a framework for creating AI agents using human-readable and LLM-executed playbooks. It uses a patent-pending natural language program execution engine.

**Status**: Playbooks AI is still in early development. It is not yet ready for production use. We are working hard and would love to get your feedback and contributions.

## Table of Contents

- [Show me!](#show-me)
- [Why Playbooks?](#why-playbooks)
- [Features](#features)
- [How it works](#how-it-works)
- [Quick start](#quick-start)
- [Who Should Use Playbooks?](#who-should-use-playbooks)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Contributors](#contributors)

## Show me!

Well, here is a hello world agent that uses a single playbook:

```playbooks
# Hello World Agent

## HelloWorldPlaybook

### Trigger
At the beginning of a conversation

### Steps
- Greet the user with a friendly "Hello, World!" message.
```

Simple, right?

Here's a more complex example... It defines a safe, comprehensive web search chat agent - uses external tool, a few playbooks, parallel tool calling and an iterative, complex RAG flow, trigger-driven playbook execution and a lot more. See the [Web Search Chat](examples/playbooks/web_search_chat.md) Playbooks AI agent.

Now take a look at the LangGraph implementation of the same agent: [LangGraph implementation](examples/langgraph/web_search_chat.py). Crazy, right? And despite the complex implementation, it is still more [rigid and brittle](examples/langgraph/web_search_chat.md) compared to the Playbooks AI agent!

## Why playbooks?

It all started with a simple question - Why can't we train AI agents just like we train human agents using training material that gives them basic information and a few playbooks to follow?

One of the biggest challenges in building and using AI agents today is the difficulty specifying and modifying agent behavior. If agents are configured using code, it is hard for business users to make changes. On the other hand, if a UI based configuration system is used, such systems typically lack fluidity and offer limited customizability, which makes them not suitable for Enterprise use. One can be brave and write complex prompts to configure agents, but LLMs cannot follow such prompts faithfully! Can't use code, can't use UI builders, can't use complex prompts - what can we do?

We need a mechanism to configure AI agents that is easy to understand and modify, leverages LLM's ability to make intelligent decisions, while ensuring adherance to the provided guidelines.

Playbooks is the perfect middle ground. Agent behavior is written in an easily readable English-like pseudocode, and the framework takes care of advanced capabilities like 
- ensuring proper step by step control flow, 
- calling internal (other playbooks) and external (APIs) tools, 
- managing complex behaviors written using 100s or 1000s of playbooks, 
- multi-agent communication, 
- external event triggered playbooks, and so on. 

Not only that, business users can use a copilot that can transparently make changes to the playbooks on their behalf, enabling them to easily make changes to agent behavior, such as listing caveats and special cases, adding new business logic, and so on.

## Features

### Everyone can build AI agents with playbooks
- Write AI agent behavior using natural language playbooks instead of using code or using a UI builder
- Non-technical business users can understand and modify agent behavior as business realities change
- Talk with a copilot to modify playbooks and review changes

### Powerful agentic behavior
- Playbooks AI agents faithfully follow your instructions, overcoming LLM limitations
- Build complex agent behavior using 100s or 1000s of playbooks
- Easy to create multi-agent systems
- Easy to call external tools
- Magical dynamic triggering of playbooks to handle validations, caveats, special cases, and so on
- External event triggered playbooks

### Infinite possibilities

- Playbooks AI agent can be used to build agentic AI applications like:
  - Chatbots
  - Customer support agents
  - Virtual assistants
  - Virtual team members
  - Intelligent workflow automation
- Easy to use for simple and complex use cases, both standalone and integrated with other systems

What will you build with Playbooks AI?

## Quick start

3 easy ways to try out playbooks:

1. Visit [runplaybooks.ai](https://runplaybooks.ai) and try out the demo playground

2. On command line

```bash
pip install playbooks
poetry run python src/playbooks/applications/agent_chat.py examples/playbooks/chat.md --stream
```

## Who Should Use Playbooks?

Playbooks AI is designed for anyone looking to build and control AI agents with ease. It is ideal for:

✅ Developers & AI Engineers – Create, test, and deploy LLM-powered agents with structured, human-readable playbooks.

✅ Businesses & Enterprises – Configure AI agents without coding while maintaining full control over behavior and workflows.

✅ AI Researchers & Experimenters – Prototype and iterate on multi-agent collaboration and reasoning models efficiently.

✅ Product Teams & No-Code Enthusiasts – Modify agent behavior without diving into complex prompts or code.

✅ Automation Specialists – Use Playbooks AI for process automation, API integrations, and intelligent workflows.

If you want a flexible, scalable, and human-readable way to define AI agent behavior, Playbooks AI is the right tool for you! 🚀


## Roadmap

We're just getting started! There's a lot we are planning to do to make Playbooks AI the best way to build and run AI agents. Here’s what’s coming next:

- Playbooks Observer for monitoring and debugging
- Playbooks Hub for community playbooks and agents
- VSCode extension for Playbooks debugging
- Dynamic filtering of playbooks
- Interop with other AI agent frameworks
- Multi-agent natural language communication
- Playbooks evaluation dataset
- Inference speed optimizations
- Running tools in a sandbox
- Command line tooling improvements
- PlaybooksLM fine-tuned model for executing playbooks
- Expanded set of examples
- Documentation generation
- Playbooks Platform with enterprise-grade features

## Contributing

Welcome to the Playbooks community! We're excited to have you contribute. 

If you want to help, checkout some of the issues marked as `good-first-issue` or `help-wanted` found [here](https://github.com/playbooks-ai/playbooks/labels/good%20first%20issue). They could be anything from code improvements, a guest blog post, or a new cookbook.

### Development Environment Setup

1. **Clone the Repository**
   ```bash
   git clone https://github.com/playbooks-ai/playbooks.git
   cd playbooks
   ```

2. **Environment Variables**
   Set up environment variables for the playbooks package (`.env`):
   ```bash
   cp .env.example .env
   ```

   Edit `.env` to configure LLM and API settings.

3. **playbooks Python package Setup**
   ```bash
   # Create and activate a virtual environment (recommended)
   
   python -m venv venv # or conda create -n venv python, or pyenv virtualenv venv

   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install playbooks Python package in development mode
   pip install poetry
   poetry install
   ```
   
### Testing

We use pytest for testing. Here's how to run the tests:

1. **Run playbooks Python Package Tests**
   ```bash
   pytest
   ```

### Getting Help

- Join our [Discord community](https://discord.com/channels/1320659147133423667/1320659147133423670)
- Check existing issues and discussions
- Reach out to maintainers

We appreciate your contributions to making Playbooks better! If you have any questions, don't hesitate to ask.

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

This project is maintained by [Playbooks AI](https://runplaybooks.ai).