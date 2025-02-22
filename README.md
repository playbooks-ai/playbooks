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

Let’s start simple. Here’s a Hello World AI agent written in Playbooks AI:

```playbooks
# Hello World Agent

## HelloWorldPlaybook

### Trigger
At the beginning of a conversation

### Steps
- Greet the user with a friendly "Hello, World!" message.
```

Simple, right? Just plain English defining AI behavior, no code required.

Now, let’s take it further. Imagine building a real-world AI agent that:

- Uses web search when needed
- Performs iterative deep research to gather and present information
- Rejects unsavory conversation topics

See [Playbooks AI implementation](examples/playbooks/web_search_chat.md) of a Web Search Chat agent — about **50 lines of English instructions**. This agent:

- uses external tools
- implements an iterative, complex RAG flow
- demonstrates parallel tool calling
- demonstrates trigger-driven playbook execution

Now compare that with an equivalent [LangGraph implementation](examples/langgraph/web_search_chat.py) — about **200 lines of complex code** that is hard to understand and modify, and yet, the resulting agent behavior is less flexible than the Playbooks AI agent!

🔗 Want to build your AI application using playbooks? [Get started here](#quick-start).

## Why Playbooks?

Ever tried configuring an AI agent and thought, *"This is way harder than it should be"*? You’re not alone.

Building AI agents today requires choosing between **three frustrating options**:
1. **Code-based frameworks** (LangGraph, CrewAI, AutoGen, etc.) → Powerful but require deep technical expertise.
2. **No-code UI-based agent builders** (Voiceflow, Botpress, Vertex AI, Copilot Studio, Kore.ai, etc.) → Easy to start but quickly become a tangled mess.
3. **Direct prompting** (Chain-of-Thought, Self-Consistency, Tree-of-Thoughts, etc.) → Seem intuitive but resulting behavior is unpredictable and brittle.

We thought: *Why not train AI agents like we train human agents?* 

Imagine **onboarding** a customer support agent. Instead of writing thousands of lines of Python or dragging boxes in a UI, **you give them playbooks** to follow — structured, human-readable guides that include step-by-step procedures, caveats, and tips & tricks. What if you could do the same for onboarding an AI agent? **Now you can do that with Playbooks AI.** 

✅ **Define AI behavior in plain English**  
✅ Business users can read, modify, and adapt workflows  
✅ Handles step-by-step execution, external API calls, and multi-agent collaboration  

Think of it as writing pseudocode that actually runs — without complex state machines or hidden LLM hallucinations.

### **Playbooks AI vs. other approaches for building AI agents**

| Feature                 | **Playbooks AI** 🏆 | **Code-Based Frameworks** | **UI-Based Agent builders** | **Direct Prompting** |
|-------------------------|------------------|-------------------------------|-------------------------------|-------------------------------|
| **Ease of Use**         | ✅ Simple, human-readable playbooks | ❌ Requires Python & async expertise | ✅ No-code UI, but complex flows are hard to maintain | ✅ Easiest — just type a prompt |
| **Behavior Tunability** | ✅ Easily modify agent behavior | ❌ Requires coding expertise to modify | ❌ Hard to translate requirements into UI workflows | ❌ Difficult to get the right behavior |
| **Workflow Complexity** | ✅ Handles simple & complex logic | ✅ Handles complex logic, but requires coding expertise | ❌ Hard to scale beyond simple workflows | ❌ No structured execution, LLM follows instructions loosely |
| **External API Calls**  | ✅ Simple, declarative tool calling | ✅ Explicit tool calling | ✅ Often requires prebuilt integrations | ❌ Needs manual copy-pasting of results, no automation |
| **Workflow Scalability** | ✅ Designed to handle 100s-1000s of playbooks | ✅ No limit, but code complexity grows exponentially | ❌ UI-based logic becomes unmanageable for large workflows | ❌ Cannot scale beyond one-off conversations |
| **Business User Usability**     | ✅ Yes | ❌ No, complex code | ❌ No, complex workflow graphs | ❌ No, complex prompt engineering |

---

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


## Roadmap

We're just getting started! There's a lot we are planning to do to make Playbooks AI the best way to build and run AI agents. Here’s what’s coming next:

- Playbooks Observer for observability and debugging
- Online planning by generating playbooks
- Process multiple trigger matches simultaneously
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