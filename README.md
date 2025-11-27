<div align="center">
   <h1>
   <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://playbooks-ai.github.io/playbooks-docs/assets/images/playbooks-logo-dark.png">
      <img alt="Playbooks AI" src="https://playbooks-ai.github.io/playbooks-docs/assets/images/playbooks-logo.png" width=200 height=200>
   </picture>
  <h2 align="center">Playbooks AI<br/>LLM is your new CPU<br/>Welcome to Software 3.0</h2>
</div>

<div align="center">

[![GitHub License](https://img.shields.io/github/license/playbooks-ai/playbooks?logo=github)](https://github.com/playbooks-ai/playbooks/blob/master/LICENSE)
[![PyPI Version](https://img.shields.io/pypi/v/playbooks?logo=pypi&color=blue)](https://pypi.org/project/playbooks/)
[![Python Version](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://www.python.org/)
[![Documentation](https://img.shields.io/badge/Docs-GitHub-blue?logo=github)](https://playbooks-ai.github.io/playbooks-docs/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/playbooks-ai/playbooks)
[![Test](https://github.com/playbooks-ai/playbooks/actions/workflows/test.yml/badge.svg)](https://github.com/playbooks-ai/playbooks/actions/workflows/test.yml)
[![Lint](https://github.com/playbooks-ai/playbooks/actions/workflows/lint.yml/badge.svg)](https://github.com/playbooks-ai/playbooks/actions/workflows/lint.yml)
[![GitHub issues](https://img.shields.io/github/issues/playbooks-ai/playbooks)](https://github.com/playbooks-ai/playbooks/issues)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-green.svg)](https://github.com/playbooks-ai/playbooks/blob/master/CONTRIBUTING.md)
[![Contributors](https://img.shields.io/github/contributors/playbooks-ai/playbooks)](https://github.com/playbooks-ai/playbooks/graphs/contributors)

[![Homepage](https://img.shields.io/badge/Homepage-runplaybooks.ai-red?logo=google-chrome)](https://runplaybooks.ai/)
</div>

> **Playbooks is a framework and runtime for building verifiable multi-agent AI systems with Natural Language Programs.**

Describe what your agents should do, not how to do it. Focus on agent behavior at a high level while the LLM handles implementation details and edge cases. Mix natural language and Python seamlessly on the same call stack. Get verifiable execution, full observability, and programs that business users can actually read and approve.

Here's a complete **29-line Playbooks program** that orchestrates natural language and Python code together. Notice how the `Main` playbook (line 4) calls Python function `process_countries` (line 20), which then calls natural language playbook `GetCountryFact` (line 27).
````markdown linenums="1" title="country-facts.pb"
# Country facts agent
This agent prints interesting facts about nearby countries

## Main
### Triggers
- At the beginning
### Steps
- Ask user what $country they are from
- If user did not provide a country, engage in a conversation and gently nudge them to provide a country
- List 5 $countries near $country
- Tell the user the nearby $countries
- Inform the user that you will now tell them some interesting facts about each of the countries
- process_countries($countries)
- End program

```python
from typing import List

@playbook
async def process_countries(countries: List[str]):
    for country in countries:
        # Calls the natural language playbook 'GetCountryFact' for each country
        fact = await GetCountryFact(country)
        await Say("user", f"{country}: {fact}")
```

## GetCountryFact($country)
### Steps
- Return an unusual historical fact about $country
````

This accomplishes the same task as implementations that are [significantly longer and more complex using traditional agent frameworks](https://playbooks-ai.github.io/playbooks-docs/reference/playbooks-traditional-comparison/#traditional-framework-implementation-272-lines).

![Playbooks](https://docs.runplaybooks.ai/assets/images/playbooks-illustrated.jpeg)

## What is Software 3.0?

Software 3.0 is the evolution from hand-coded algorithms (Software 1.0) and learned neural network weights (Software 2.0) to **natural language as the primary programming interface**. 

In Playbooks, you write programs in human language that execute directly on large language models. The LLM acts as a semantic CPU that interprets and runs your instructions. Instead of translating business logic into formal code syntax or training models on data, you describe what you want in natural language, mix it seamlessly with Python when needed, and get verifiable, observable execution. 

This changes how you build AI systems: business stakeholders can read and approve the actual program logic, AI systems become transparent rather than black boxes, and sophisticated agent behaviors become accessible without sacrificing control or understanding.


## Why Playbooks?

- **Think at a Higher Level**
: Focus on what your agent should do, not implementation mechanics. Define complex, nuanced behaviors without getting lost in orchestration details. The framework handles the low-level execution.

- **Natural Exception Handling**
: The LLM handles edge cases and exceptional conditions smoothly without explicit code for every contingency. Your agents adapt to unexpected situations naturally.

- **Powerful Abstractions**
: Multi-agent meetings for complex coordination. Triggers for event-driven behavior. Seamless mixing of natural language and Python. Abstractions that would take hundreds of lines in other frameworks are built-in.

- **Readable by Everyone**
: Business stakeholders can read and approve the actual program logic. No more "black box" AI systems. What you write is what executes.

- **Verifiable & Observable**
: Unlike prompt engineering where you hope the LLM follows instructions, Playbooks guarantees verifiable execution. Step debugging in VSCode, detailed execution logs, full observability.


## Get Started in 10 Minutes

Build your first AI agent with Playbooks. You'll need Python 3.12+ and an [Anthropic API key](https://console.anthropic.com/settings/keys).

### Install Playbooks

```bash
pip install playbooks
```

### Run the Country Facts Example

Try the more advanced example from above:

```bash
playbooks run country-facts.pb
```

You can also use the **Playground** for interactive development:

```bash
playbooks playground
```

The Playground provides a visual interface to run programs, view execution logs, and iterate quickly.

### Step Debugging in VSCode

For production development, install the **Playbooks Language Support** extension:

1. Open VSCode Extensions (Ctrl+Shift+X / Cmd+Shift+X)
2. Search for "Playbooks Language Support"
3. Click Install

Now you can set breakpoints and step through your agent's execution, just like traditional code!

## 📚 Documentation

Visit our [documentation](https://playbooks-ai.github.io/playbooks-docs/) for comprehensive guides, tutorials, and reference materials.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the latest updates.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributors
We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->
<!-- ALL-CONTRIBUTORS-LIST:END -->
<a href="https://github.com/playbooks-ai/playbooks/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=playbooks-ai/playbooks" />
</a>

