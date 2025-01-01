<div align="center">
  <img src="./website/frontend/public/playbooks-logo-only.png" alt="Logo" width="300">
  <h1 align="center">Playbooks AI</h1>
</div>


<div align="center">
   <a href="https://pypi.org/project/playbooks/">
      <img src="https://img.shields.io/pypi/v/playbooks?logo=pypi&style=plastic&color=blue" alt="PyPI Version"></a>

   <a href="https://www.python.org/">
      <img src="https://img.shields.io/badge/Python-3.12-blue?style=plastic&logo=python" alt="Python Version"></a>

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
  <h2 align="center">Train AI Agents Like Humans</h2>
</div>

Playbooks AI is a framework for creating AI agents using human-readable and LLM-executed playbooks.

## Quick start

3 easy ways to try out playbooks:

1. Visit [runplaybooks.ai](https://runplaybooks.ai) and try out the demo playground

<!-- 2. On command line:

```bash
pip install playbooks
playbooks run hello.md
``` -->

2. In Python REPL

   a. Install the playbooks Python package
   ```bash
   pip install playbooks
   ```

   b. Try running a simple playbook
   Start Python REPL -

   ```bash
   python
   ```

   Paste the following code with your Anthropic API key -

   ```python
   import asyncio
   import playbooks

   playbook = """
   # HelloWorld Agent
   This is a simple Hello World agent.

   ## HelloWorld

   ### Trigger
   When the user starts a conversation or asks for a greeting.

   ### Steps
   - Greet the user with a friendly "Hello, World!" message.
   - Explain that this is a demonstration of a simple Hello World playbook.
   - Say goodbye to the user. 
   """

   print(
      asyncio.run(
         playbooks.run(
               playbook,
               model="claude-3-5-sonnet-20241022",
               api_key="<YOUR ANTHROPIC API KEY>",
         )
      )
   )
   ```


Now, try modifying the hello.md playbook to greet the user with "Hello Playbooks!" instead and give it a try. Easy, right?

Now take a look at some example playbooks in examples folder. Try writing your own playbooks. Don't worry, the syntax is quite flexible and forgiving.

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
   Set up environment variables for the playbooks package (`python/packages/playbooks/.env`):
   ```bash
   # LLM Configuration
   DEFAULT_MODEL=claude-3-5-sonnet-20241022
   ANTHROPIC_API_KEY=your-anthropic-api-key
   OPENAI_API_KEY=your-openai-api-key  # Optional

   # API Configuration
   PORT=8000
   HOST=0.0.0.0
   ```
3. **playbooks Python package Setup**
   ```bash
   # Create and activate a virtual environment (recommended)
   python -m venv venv # or conda create -n venv python, or pyenv virtualenv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install playbooks Python package in development mode
   cd python/packages/playbooks
   pip install poetry
   poetry install
   cd ../../..
   ```

4. **Website Setup**
   ```bash
   # Install foreman (process manager)
   sudo gem install foreman
   
   # Set up API
   cd website/api
   pip install -r requirements.txt
   cd ..
   
   # Set up Frontend
   cd frontend
   npm install
   cd ../..

   # Run the website
   cd website
   foreman start
   ```

   For detailed website development instructions, see `website/README.md`.
   
### Testing

We use pytest for testing. Here's how to run the tests:

1. **Run playbooks Python Package Tests**
   ```bash
   cd python/packages/playbooks
   pytest
   ```

2. **Run Website API Tests**
   ```bash
   cd website/api
   pytest

### Getting Help

- Join our [Discord community](https://discord.com/channels/1320659147133423667/1320659147133423670)
- Check existing issues and discussions
- Reach out to maintainers

We appreciate your contributions to making Playbooks better! If you have any questions, don't hesitate to ask.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 

# Contributors

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

<a href="https://github.com/playbooks-ai/playbooks/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=playbooks-ai/playbooks" />
</a>
