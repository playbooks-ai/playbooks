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
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/playbooks/playbooks-ai)
[![Test](https://github.com/playbooks-ai/playbooks/actions/workflows/test.yml/badge.svg)](https://github.com/playbooks-ai/playbooks/actions/workflows/test.yml)
[![Lint](https://github.com/playbooks-ai/playbooks/actions/workflows/lint.yml/badge.svg)](https://github.com/playbooks-ai/playbooks/actions/workflows/lint.yml)
[![GitHub issues](https://img.shields.io/github/issues/playbooks-ai/playbooks)](https://github.com/playbooks-ai/playbooks/issues)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-green.svg)](https://github.com/playbooks-ai/playbooks/blob/master/CONTRIBUTING.md)
[![Contributors](https://img.shields.io/github/contributors/playbooks-ai/playbooks)](https://github.com/playbooks-ai/playbooks/graphs/contributors)

[![Homepage](https://img.shields.io/badge/Homepage-runplaybooks.ai-red?logo=google-chrome)](https://runplaybooks.ai/)
</div>

**Build multi‑agent AI systems** with ease using **Python** and **natural language**.

Stop writing prompts and hoping that the LLM will follow them faithfully. Instead, get **verifiable natural language program execution** with Playbooks.

Playbooks is an innovative framework for building and executing AI agents using "playbooks" – structured workflows defined in natural language and Python code. Created by [Amol Kelkar](https://www.linkedin.com/in/amol-kelkar/), the framework is part of the world's first Software 3.0 tech stack, Playbooks AI. It includes a **new programming language** (markdown-formatted .pb files) that are compiled to Playbooks Assembly Language (.pbasm files), that are then executed by the Playbooks Runtime.

Unlike other AI agent frameworks, **Playbooks programs are highly readable**. Business users can understand, change, and approve agent behavior specified in natural language; while developers benefit from the flexibility of running Python code on CPU and natural lanuage code on LLM, on the same call stack, and with full observability and control.

---

Here is an example Playbooks program. It contains both Python and natural language "playbooks", i.e. functions. It contains a single `Country facts agent`. Notice how natural language playbook `Main` calls a Python playbook `process_countries`, which in turn calls a natural language playbook `GetCountryFact`. See equivalent [LangGraph implementation](https://playbooks-ai.github.io/playbooks-docs/reference/playbooks-traditional-comparison/).

**country-facts.pb**, an example Playbooks program -
````markdown
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

### Install Playbooks
```
# You will need Python 3.12+ and your Anthropic API key
pip install playbooks
```

### Run using Playbooks CLI
```bash
ANTHROPIC_API_KEY=sk-ant-... playbooks run country-facts.pb
```

### Run in Playbooks Playground
```bash
ANTHROPIC_API_KEY=sk-ant-... playbooks playground
```
Put your program path and click "Run Program". You can turn on "Execution Logs" to see the program execution details.

### Run programmatically
   ```python
   from playbooks import Playbooks

   pb = Playbooks(["country-facts.pb"]) # absolute or relative path
   await pb.initialize()
   await pb.program.run_till_exit()
   ```

### Step debugging in VSCode (Optional)

Install the **Playbooks Language Support** extension for Visual Studio Code:

1. Open VSCode
2. Go to Extensions (Ctrl+Shift+X / Cmd+Shift+X)
3. Search for "Playbooks Language Support"
4. Click Install

The extension provides debugging capabilities for playbooks programs, making it easier to develop and troubleshoot your AI agents. Once the plugin is installed, you can open a playbooks .pb file and start debugging!

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

