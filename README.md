<div align="center">
  <h1 align="center">Playbooks AI</h1>
  <h2 align="center">Finally, Natural Language Programming is here!</h2>
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

Playbooks AI™ lets you program AI agents using plain English instead of code. Our patent-pending engine turns human-readable instructions into executable AI behavior — no coding required.

**Status**: Playbooks AI is still in early development. We're working hard and would love your feedback and contributions.

## Table of Contents

- [Show me!](#show-me)
- [What is Natural Language Programming?](#what-is-natural-language-programming)
- [Features](#features)
- [How it works](#how-it-works)
- [Quick start](#quick-start)
- [Who Should Use Playbooks?](#who-should-use-playbooks)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Contributors](#contributors)

## Show me!

Here's the simplest Natural Language Program you can write — a Hello World agent:

```playbooks
# Hello World!

## Say Hello

### Trigger
At the beginning

### Steps
- Greet the user with a friendly "Hello, World!" message.
```

That's it! Just plain English that both humans and AI can understand. Here "Hello World!" is name of the AI agent, while "Say Hello" is a playbook. A playbook is executed as soon as its trigger condition is satisfied.

Now, let's look at something more powerful. Here's a web search agent that:

- Uses search engines when needed
- Performs deep research to gather information
- Filters out inappropriate topics

See [Playbooks AI implementation](examples/playbooks/web_search_chat.md) of a Web Search Chat agent — about **50 lines of English instructions**. 

Now compare that with an equivalent [LangGraph implementation](examples/langgraph/web_search_chat.py) — about **200 lines of complex code** that's harder to understand and modify.

🔗 Ready to write your first Natural Language Program? [Get started here](#quick-start).

## What is Natural Language Programming?

Natural Language Programming lets you create AI applications by writing instructions in plain English. Think of it as pseudocode that actually runs.

Building AI agents today forces you to choose between three frustrating options:

1. **Writing complex code** → Requires technical expertise
2. **Using no-code UI builders** → Gets messy for complex workflows
3. **Direct prompting** → Results in unpredictable behavior

With Playbooks AI, you simply write clear instructions in a playbook format that:
- Business people can read and modify
- AI can execute reliably
- Handles complex logic, tool usage, and multi-agent collaboration

### **Natural Language Programming vs. Traditional Approaches**

| Feature                 | **Playbooks AI** 🏆 | **Code-Based Frameworks** | **UI-Based Agent builders** | **Direct Prompting** |
|-------------------------|------------------|-------------------------------|-------------------------------|-------------------------------|
| **Ease of Use**         | ✅ Write in plain English | ❌ Requires Python expertise | ✅ No-code UI, but gets messy | ✅ Just type a prompt |
| **Behavior Control** | ✅ Easily modify agent behavior | ❌ Requires coding to change | ❌ Hard to translate requirements into UI | ❌ Unpredictable results |
| **Workflow Complexity** | ✅ Handles simple & complex logic | ✅ Handles complex logic, but requires coding | ❌ Hard to scale beyond simple workflows | ❌ No structured execution |
| **External API Calls**  | ✅ Simple tool calling | ✅ Explicit tool calling | ✅ Often requires prebuilt integrations | ❌ Manual copy-pasting, no automation |
| **Scalability** | ✅ Designed for 100s-1000s of playbooks | ✅ No limit, but code complexity grows | ❌ UI becomes unmanageable at scale | ❌ Cannot scale beyond one-off conversations |
| **Business User Friendly**     | ✅ Yes | ❌ No, requires coding | ❌ No, complex workflow graphs | ❌ No, requires prompt engineering |

## Features

### Write programs in plain English
- Define AI agent behavior using natural language instead of code
- Let non-technical team members understand and modify agent behavior
- Talk with a copilot to improve your natural language programs

### Powerful execution engine
- Playbooks AI faithfully follows your instructions
- Build complex behavior using hundreds or thousands of playbooks
- Easily create multi-agent systems
- Call external tools with simple language
- Dynamic triggering to handle special cases and validations
- Respond to external events

### Build any AI application

- Create a wide range of applications:
  - Intelligent chatbots
  - Customer support agents
  - Virtual assistants
  - Team automation tools
  - Workflow automation

What will you build with Playbooks AI?

## Quick start

2 easy ways to try Playbooks AI:

1. Visit [runplaybooks.ai](https://runplaybooks.ai) and try out the demo playground, OR

2. On command line

```bash
pip install playbooks
poetry run python src/playbooks/applications/agent_chat.py examples/playbooks/chat.md --stream
```

## Who Should Use Playbooks?

Natural Language Programming with Playbooks AI is perfect for:

✅ **Developers & Engineers** – Create AI agents without writing complex state machines

✅ **Business Teams** – Modify AI behavior without coding or technical expertise

✅ **Product Managers** – Quickly prototype and iterate on AI features

✅ **AI Researchers** – Experiment with multi-agent systems more efficiently

✅ **Automation Specialists** – Build intelligent workflows with API integrations

## Roadmap

We're just getting started! Here's what's coming next:

- Playbooks Observer for observability and debugging
- Online planning by generating playbooks
- Process multiple trigger matches simultaneously
- Playbooks Hub for community sharing
- VSCode extension for debugging
- Copilot for conversational playbook creation
- Multi-agent communication
- Inference speed optimizations
- Tool sandboxing
- PlaybooksLM fine-tuned model
- Playbooks Platform with enterprise features

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