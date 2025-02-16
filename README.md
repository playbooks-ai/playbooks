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

Now a more complex example. Let's see how to create a safe, comprehensive web search chat agent that:

- uses external tools
- implements an iterative, complex RAG flow
- uses a few playbooks
- demonstrates parallel tool calling
- demonstrates trigger-driven playbook execution

See the [Web Search Chat](examples/playbooks/web_search_chat.md) Playbooks AI agent.

Now, take a look at the equivalent LangGraph implementation: [LangGraph implementation](examples/langgraph/web_search_chat.py). Crazy, right? And despite the highly complex implementation, it is still more [rigid and brittle](examples/langgraph/web_search_chat.md) compared to the Playbooks AI agent!

I'll offer a few refinements to make the content even more impactful while maintaining its flow:

## Why Playbooks? 🤔

It all started with a simple question - Why can't we train AI agents the same way we train human agents? Think about how a customer support agent learns: they get documentation covering common scenarios, tips and tricks gained from experience, and specific playbooks to follow (like "when a customer reports a billing issue, first verify their account details, then..."). These playbooks guide them while leaving room for judgment. Shouldn't AI agents be trained the same way?

One of the biggest headaches in working with AI agents today is getting them to behave exactly the way we want. Here's the problem:
- If you configure agents with code, business users can't understand the expected behavior, let alone make changes as business needs evolve. Current AI agent frameworks like LangGraph, AutoGen, and CrewAI require writing complex Python code with deep knowledge of async programming, state machines, and prompt engineering. Even experienced developers need significant time to understand and modify agent behavior.
- If you use a UI-based workflow automation or AI agent builder system, the initial simplicity is deceiving. Real-world workflows quickly turn into complex, jumbled graphs that are a nightmare to build, understand, and maintain. Companies spend months building these workflow graphs only to discover they need highly skilled specialists just to make simple changes.
- If you try implementing workflows using complex step-by-step prompts that look like playbooks, well... LLMs aren't great at following those faithfully. You'll get unreliable, incomplete, and sometimes hallucinated behavior.

Can't use code, can't use UIs, can't use complex prompts - now what? 🤷

We need something that's:
- Easy to understand and modify ✍️
- Leverages LLMs' smart decision-making abilities 🧠
- Actually ensures your workflow instructions are followed ✅

That's where Playbooks AI comes in! Think of it as writing agent behavior in English-like pseudocode. The framework handles all the complex stuff behind the scenes:
- Proper step-by-step control flow
- Calling external tools and APIs at the right time
- Managing complex behaviors across hundreds or thousands of playbooks
- System complexities like multi-agent communication
- External event-triggered behaviors

But here's the best part: business users can actually read and understand playbooks. They also get a copilot that can transparently modify playbooks on their behalf. Need to add caveats? Special cases? New business logic? No problem! The copilot helps make those changes and presents them for your approval. 🎯

The result? A practical middle ground that makes powerful AI agents truly accessible and customizable for enterprise use. 🚀

## Features

### Anyone can build AI agents with playbooks
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
- Copilot for conversationally understanding and modifying playbooks
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