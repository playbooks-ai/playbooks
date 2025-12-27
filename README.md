<div align="center">
   <h1>
   <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://playbooks-ai.github.io/playbooks-docs/assets/images/playbooks-logo-dark.png">
      <img alt="Playbooks AI" src="https://playbooks-ai.github.io/playbooks-docs/assets/images/playbooks-logo.png" width=200 height=200>
   </picture>
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

**Playbooks is a semantic programming system for AI agents**

![Playbooks Architecture](https://docs.runplaybooks.ai/assets/images/playbooks-illustrated.jpg)

Playbooks is a programming language, a stable semantic intermediate representation (PBAsm), and a runtime for building and running AI agents.

It treats large language models as **semantic execution engines (similar to CPUs)**.
You write programs that describe *intent and behavior*, compile them into a semantic instruction set, and execute them on a runtime that owns control flow, context, time, and autonomy.

This enables AI systems that are:

* long-lived and resumable
* inspectable and debuggable
* safe to pause, wait, and recover
* tuned to desired autonomy level
* forward-compatible as models improve

Playbooks is built for that moment when building AI agents as rigid workflows or unreliable ReAct loops becomes a challenge.

> Strict determinism is the wrong abstraction for AI systems.
> AI systems need predictable behavior and outcomes, even though their internal reasoning and execution may be probabilistic.

## What Playbooks is

Playbooks consists of **three inseparable parts**:

### 1. A human-readable programming language

Programs are written in structured natural language, with optional Python for deterministic logic.

These are **executable specifications**, not prompts.

### 2. A semantic intermediate representation (PBAsm)

Programs compile into PBAsm — a low-level instruction set designed specifically for LLM execution.

PBAsm defines:

* explicit call stacks and execution frames
* yields, waits, and interrupts
* scoped variables and lifetimes
* resumable execution boundaries

This intermediate representation is what makes structured context management and forward compatibility possible. The compiler ensures that the same program can be executed on various LLMs, including future models. This is similar to how LLVM ensures that the same code can be executed on various CPUs, including future ones.

Note that PBAsm standardizes execution structure and contracts, while the model supplies the reasoning.

PBAsm represents a Common Language Specification (CLS) for AI systems — a shared execution contract independent of any one framework. PBAsm is intentionally small: it standardizes execution structure (frames, yields, calls, returns, scopes), not model semantics. We welcome the community to build transpilers from other agent frameworks to PBAsm, so applications built using those frameworks can be executed on the Playbooks runtime.

### 3. An execution runtime

The Playbooks runtime:

* can execute specified control flow reliably, unlike prompt-based approaches
* manages context using execution call stack frames, not as an ever-growing prompt
* treats time and waiting as first-class primitives
* enforces autonomy boundaries
* executes guardrailed, just-in-time generated code
* manages agent lifecycle and communication

You get workflow intent adherence, along with adaptability and resilience.

Similar to Java or .NET virtual machines, the Playbooks runtime is a virtual machine and the Common Language Runtime (CLR) for AI systems.

## A minimal example (example.pb)
Playbooks programs are written in markdown. Each # defines an agent, ## defines a playbook. Optional python playbooks are functions decorated with @playbook. Natural language and python playbooks execute on the same call stack.

````markdown
# Facts about nearby countries
This program prints interesting facts about nearby countries

## Main
### Triggers
- At the beginning
### Steps
- Ask user what $country they are from
- If user did not provide a country, engage in a conversation and gently nudge them to provide a country
- List 5 $countries near $country
- Tell the user the nearby $countries
- Inform the user that you will now tell them some interesting facts about each of the countries
- Process the $countries
- End program

```python
from typing import List

@playbook
async def process_countries(countries: List[str]):
  # Python loop iterates through the list provided by the NL playbook
  for country in countries:
    # Python calls the NL playbook 'GetCountryFact' for each country
    fact = await GetCountryFact(country)
    await Say("user", f"{country}: {fact}")
```

## GetCountryFact($country)
### Steps
- Return an unusual historical fact about $country
````

This program:

* mixes natural language and Python on the same call stack
* pauses safely for user input
* resumes from a well-defined execution point
* remains readable and reviewable

What you read is what actually runs.

## Why Playbooks exists

Most agent systems today fall into one of two camps:

* Python workflows orchestrating LLM calls (LangGraph, AutoGen, ADK, Strands, etc.), or
* model-centric loops where the model remains the primary orchestrator (ReAct-style agents, Claude Skills-style procedural packages, etc.)

Today's agent frameworks become challenging as systems grow, because:

* control flow determinism and reasoning fluidity are forced to compete in the same abstraction layer
* it is the engineer's responsibility to manage LLM context, and that becomes increasingly complex and error-prone as systems become more complex
* agent behavior needs non-trivial mental transformation into checkpointable, reentrant workflow code
* **behavior ossifies around the capabilities of today’s LLMs**

Playbooks takes a different approach:

> **Programs are stable.  
> Execution improves as LLMs improve.**

As models get better, Playbooks programs automatically get better — without rewriting orchestration logic, retries, or compensations. This is similar to the approach taken by Claude Skills, but with a more principled foundation.

## What Playbooks is *not*

* Not a prompt framework, graph builder, or no-code tool
* Not an AI coding assistant
* Not *just* another agent framework

Playbooks overlaps with agent frameworks, but operates at a deeper layer.

It is closer to:

* a programming language
* a semantic VM
* an execution target for AI software

Think **LLVM + a runtime**, not “just another agent framework”.

## When Playbooks makes sense

Playbooks is useful in **two related situations**.

### 1. Designing agent behavior clearly and iterating fast

Playbooks makes it easy to express and review agent behavior:

* Subject-matter experts can write playbooks (SOPs) to test and iterate on the behavior
* Engineers get precise behavior specifications
* Diffs show *what the agent does*, not orchestration plumbing
* Iteration happens at the level of intent, not implementation details

Teams use Playbooks here like a **design system for agent behavior** — similar to how Figma is used for UI design.

During development, these designs are executed using the Playbooks runtime. Once the behavior is stable, engineers can either:

* productionize directly using the Playbooks runtime, or
* treat it as a behavior specification and implement in another framework, if your organization has a preferred agent framework.

### 2. Running long-lived, reliable AI systems

Playbooks becomes essential when AI systems must:

* run for hours, days, or weeks
* pause and resume safely
* wait for humans or external events
* survive failures and restarts
* explain *where* they are and *why*
* remain stable as models improve

At this point, teams run production agents using the Playbooks runtime.

## When you probably don’t need Playbooks

If your system:

* has a single, real-time human-in-the-loop
* uses a single AI agent
* does not need auditability or verifiability

...then a lighter-weight framework is likely sufficient.

Playbooks is optimized for systems that **outgrow** that phase.

## Getting started

```bash
pip install playbooks
playbooks run example.pb
```

Visit our [documentation](https://docs.runplaybooks.ai) for comprehensive guides, tutorials, and reference materials.

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

