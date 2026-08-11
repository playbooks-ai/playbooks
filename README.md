<div align="center">
   <h1>
   <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://playbooks-ai.github.io/playbooks-docs/assets/images/playbooks-logo-dark.png">
      <img alt="Playbooks AI" src="https://playbooks-ai.github.io/playbooks-docs/assets/images/playbooks-logo.png" width=200 height=200>
   </picture>
  <h2 align="center">Playbooks AI<br/>LLM is your new CPU</h2>
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

> **Write what your AI agent should do, in English. Playbooks compiles it and runs it.**

Playbooks programs are markdown. The compiler turns them into a semantic instruction set, and the runtime executes it on an LLM with a real call stack, step debugging, and control flow you can actually verify. Natural language and Python run side by side in the same program.

## Hello world

Save this as `hello.pb`:

```markdown
# Hello world
This is a hello world demo for the playbooks system

## Hello world demo
This playbooks demo prints a hello playbooks message

### Triggers
- At the beginning

### Steps
- Greet the user with a hello playbooks message
- Tell the user that this is a demo for the playbooks system
- Say goodbye to the user
- End program
```

Run it:

```bash
playbooks run hello.pb
```

That is a complete program, not pseudocode. `#` declares an agent, `##` declares a playbook, and a playbook runs when its trigger fires.

## Natural language and Python, same call stack

Playbooks get interesting when the two kinds of code call each other. Below, the `Main` playbook (English) calls `process_countries` (Python), which calls `GetCountryFact` (English) once per country. All three share one call stack and one set of variables.

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

Twenty-nine lines. The [equivalent agent in a traditional framework runs 272 lines](https://playbooks-ai.github.io/playbooks-docs/reference/playbooks-traditional-comparison/#traditional-framework-implementation-272-lines).

Notice what is not in the program: no orchestration graph, no state machine, no retry logic, no output parsers. If the user answers the country question with a joke, you do not write a branch for it. The LLM handles it and execution continues at the next step.

![Playbooks](https://docs.runplaybooks.ai/assets/images/playbooks-illustrated.jpg)

## Get started in 10 minutes

You will need Python 3.12+ and an [Anthropic API key](https://console.anthropic.com/settings/keys).

### Install

```bash
pip install playbooks
```

### Set your API key

```bash
export ANTHROPIC_API_KEY=your-anthropic-api-key
```

You can also put it in a `.env` file. See `.env.example` for the other supported providers.

### Run a program

```bash
playbooks run hello.pb
```

Add `-v` to print the session log, or `--snoop=true` to watch messages pass between agents.

### Try the playground

```bash
playbooks playground
```

The playground gives you a browser interface for running programs, reading execution logs, and iterating quickly.

### Step through it in VSCode

Install the **Playbooks Language Support** extension:

1. Open Extensions (Ctrl+Shift+X / Cmd+Shift+X)
2. Search for "Playbooks Language Support"
3. Click Install

Now open a `.pb` file and set a breakpoint on an English step. You get breakpoints, a call stack, and variable inspection on a natural language program, the same way you would debug Python.

## Why Playbooks?

**You describe behavior, not mechanics.** Say what the agent should do. The runtime handles sequencing, context, and recovery.

**Edge cases do not need code.** The LLM deals with the unexpected conversation turn instead of you writing a branch for it.

**Anyone can read the program.** The person who owns the process can read the actual logic that runs and tell you it is wrong. There is no separate spec that drifts from the implementation.

**Execution is verifiable.** Playbooks does not hope the LLM follows your instructions. It compiles them, executes them against a call stack, and logs what happened.

**Context does not grow forever.** When a playbook returns, its execution trace collapses into its return value. The caller sees the result, not the transcript.

**Bigger abstractions are built in.** Multi-agent meetings, event-driven triggers, agents as classes with real methods and state, and time and waiting as first-class primitives.

## What is Software 3.0?

Software 1.0 is code you write. Software 2.0 is weights you train. Software 3.0 is the program written in human language and executed directly by a model acting as a semantic CPU.

Playbooks is a bet on the third one: that the specification should be the program, and that the same program should get better as models get better, without you rewriting the orchestration around it.

## Documentation

Visit the [documentation](https://playbooks-ai.github.io/playbooks-docs/) for guides, tutorials, and reference material.

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
