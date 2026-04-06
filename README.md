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

---

# -- Sunsetting Playbooks --

## Lessons from Building a Natural Language Programming System for AI Agents

*By Amol Kelkar | April 2026*

---

I'm sunsetting [Playbooks](https://github.com/playbooks-ai/playbooks), the open-source semantic programming system for AI agents that I've been building since mid-2022.

The most important lesson from this project is also its most ironic: Playbooks championed the principle that agent specifications should be *forward compatible*---that old programs should automatically get better when the underlying model improves. That principle is correct. And it's precisely why a simpler approach was always going to win. An agent harness with less scaffolding benefits more from model improvement than one with more. Playbooks built the most sophisticated natural language execution infrastructure of any agent framework---compiler, intermediate representation, execution validation---and then articulated the principle that explains why all that infrastructure would eventually be unnecessary.

That's the story of this project. Here's how it unfolded.

## The Origin

Playbooks began in June 2022 when I started experimenting with GPT-3 to build customer support agents that needed both structured behavior and human-like flexibility. Traditional approaches---imperative code, visual workflow builders like DialogFlow CX, story-based systems like Rasa---couldn't handle the nuance these agents needed. I became obsessed with a question: **what if English itself could be the programming language, and LLMs could be the CPUs that execute it?**

That obsession became Playbooks: a structured markdown language for specifying agent behavior, a semantic intermediate representation (PBAsm) that compiled those specs into executable instructions, and a runtime that managed execution with the determinism of traditional software and the flexibility of LLMs. The project went through four complete system rewrites, was initially open-sourced in early 2023, and shipped 16 releases through v0.7.4 in February 2026.

## Why Sunset Now?

The generalist agent + skills approach has won. And the approach that won is the one Playbooks helped pioneer: natural language specifications that define agent behavior, interpreted by an LLM at runtime. The industry has converged on this paradigm. What's changed is the representation. Playbooks as a specific format has been supplanted by skills, Anthropic's simpler, free-form alternative that's now the de facto standard.

Skills are free-form natural language specifications that a harness loads and an LLM follows. No compiler. No assembly language. No execution validation. A skill can encode knowledge, process, caveats, edge case guidance---whatever you want. Playbooks encodes process: steps, control flow, triggers. Both are markdown. The structure difference is minimal. But skills' free-form expressiveness, combined with the rise of capable coding agents (Claude Code, Codex, Cursor, Windsurf, etc.), won the ecosystem.

Anthropic announced skills on October 16, 2025. The practical question became not "which specification method is better?" but "which one has ecosystem momentum?"

## Key Technical Ideas

Several ideas that Playbooks explored have since appeared in the broader ecosystem, often in different form, sometimes independently invented. These build on a long history of work in multi-agent systems, conversational AI, and business rule engines, but their combination in the LLM agent context was, as far as I can tell, new. Here's what I think is worth preserving.

### Natural Language as a Programming Language (June 2022 onward)

Not "prompt engineering." An actual programming language with variables, control flow, function calls, return values, and a type system, all expressed in structured natural language and compiled to a semantic intermediate representation.

When I started this work in June 2022, the industry's idea of "agent development" was chaining API calls in Python. LangGraph, CrewAI, and AutoGen didn't exist yet (all three launched between May 2023 and early 2024). OpenAI function calling wouldn't arrive until June 2023. Anthropic tool use wouldn't enter beta until April 2024. When I wrote [Realizing the Dream of Natural Language Programming](https://www.runplaybooks.ai/blog/realizing-the-dream-of-natural-language-programming) in October 2025, the idea that you could write `$order_id:str = Ask user for their order ID` and have it compile to typed, executable instructions with yield points was new in the LLM agent context. A 29-line Playbooks program [replaced 272+ lines of LangGraph](https://www.runplaybooks.ai/blog/realizing-the-dream-of-natural-language-programming) for an equivalent customer support agent---though lines-of-code comparisons across paradigms should be taken with a grain of salt, since the natural language spec pushes complexity into the runtime and LLM.

Anthropic's skills achieve something similar---natural language that agents follow---but without the compilation step or formal semantics. They trade verifiability for expressiveness and simplicity. That's a valid tradeoff for most use cases, especially as LLMs continuously improve their instruction-following reliability.

### Software Engineering Paradigm for Agents

Playbooks brought standard software engineering concepts to agent development. Agents are classes. Playbooks are methods. Public playbooks are public methods. Exported playbooks are mixins. Agent state is instance variables. Triggers are events, specified using decorators. The call stack is a real call stack.

The industry standardized on a different abstraction: "tools." An LLM has a bag of tools it can call. This is fine for simple agents, but it's a flat abstraction---no encapsulation, no hierarchy, no lifecycle management, no scoping. Class-based modeling of agents has a long history in multi-agent systems research (JADE, SPADE, and others), but applying it specifically to LLM agents with natural language methods was, as far as I'm aware, unique to Playbooks.

Anthropic's December 2024 "Building Effective Agents" blog post emphasized workflows and orchestration patterns, but the underlying primitive remained tool calls. The realization that "tools" are an arbitrary construct has slowly dawned on the industry, and as of April 2026, "code mode" agents are becoming the norm, where agents use JIT coding instead of tool calling.

### VSCode Debugging of Natural Language Programs (May 2025)

Playbooks shipped a full VSCode debugger integration in May 2025 (v0.4.0). You can set breakpoints on natural language steps, inspect the call stack, examine variables, and step through execution---on natural language programs.

```json
{
  "type": "playbooks",
  "request": "launch",
  "name": "Launch Playbook",
  "program": "${file}",
  "stopOnEntry": true
}
```

LangGraph Studio (August 2024) offered graph visualization and state editing, but that's debugging a graph, not debugging natural language. Microsoft's AI Toolkit Agent Inspector (February 2026) brought F5 debugging to code-based agent workflows, which is useful but targets a different problem. The concept of stepping through human-readable specifications has history in business rule management systems, but applying it to LLM-executed natural language programs required a runtime that could map natural language steps to debuggable execution points. PBAsm's hierarchical line numbering (01, 01.01, 01.01.01) made this possible.

The skills ecosystem has no equivalent. When a skill doesn't do what you expect, you read the markdown and try to figure out what the LLM misunderstood. For simple skills this is fine. For complex multi-step workflows, it's a gap that may close as models improve or may need to be addressed with new tooling.

### Triggers as Event-Driven Interrupts (May 2025)

Playbooks has a trigger system that works like CPU interrupts:

```markdown
### Triggers
- When user provides $email
- After calling ProcessPayment
- When $attempts > 3
- If user is extremely frustrated
```

The LLM continuously evaluates trigger conditions during execution. When one fires, the runtime saves state, invokes the handler, and resumes. This supports temporal triggers, state-based triggers, sentiment-based triggers, and cross-agent triggers.

AutoGen v0.4 (January 2025) adopted an extensible event-driven architecture, but its events are primarily system-level---message arrival, task completion---not semantic conditions evaluated by the LLM during execution. Claude Code hooks trigger on lifecycle events (PreToolUse, PostToolUse, Stop). Few agent frameworks have attempted continuous LLM-monitored ambient conditions as first-class triggers. Agents today mostly react to explicit tool calls or user messages, not to conditions like "is the user frustrated?" evaluated during execution.

### Semantic Intermediate Representation / PBAsm

PBAsm is a low-level instruction set for natural language programs, standardizing explicit call stacks, yields, interrupts, scoped variables with lifetimes, and resumable execution boundaries.

The analogy is LLVM: just as LLVM IR lets the same C program run on different CPU architectures, PBAsm lets the same natural language program run on different LLMs with consistent semantics. A natural language instruction like "Ask user for their name" compiles to:

```
01:QUE Say(user, Ask user for their $name:str); YLD for user
```

The concept of a semantic IR for natural language programs remains largely unexplored. PBAsm was designed for a world where LLMs needed structural guardrails to execute reliably. As models improve, the need for those guardrails diminishes for most applications. Whether that holds for enterprise-grade workflows requiring auditability and formal verification is an open question---and it's worth acknowledging that formal methods and inherently ambiguous natural language exist in genuine tension.

### Stack-Based Context Management

Traditional ReAct agents accumulate context linearly. Every step, tool result, and reasoning trace appends until the context window fills, then gets forcibly summarized.

Playbooks treats LLM context like a call stack. When a nested playbook completes, its detailed execution trace compresses into a compact return value. The parent only sees the summary. This cascades upward, keeping context lean and relevant at every level.

This is architecturally impossible in frameworks that orchestrate from Python without structural knowledge of what should persist in the LLM's context window. As of April 2026, most agents still accumulate context linearly and rely on ever-expanding context windows. This works today with million-token windows, but it imposes a token cost that stack-based management eliminates.

### Other Notable Capabilities

**Five playbook types** optimized for different needs: Markdown Playbooks for structured workflows, ReAct Playbooks for dynamic reasoning, Raw Prompt Playbooks for single-shot LLM calls, Python Playbooks for deterministic logic, and External Playbooks for MCP integration. All five can call each other seamlessly.

**Natural Language + Python on the same call stack.** A natural language playbook can call a Python function that calls another natural language playbook, all sharing the same execution context and variables. Skills can invoke tools including code execution, but the seamless interleaving on a shared call stack is unique.

**Incremental code execution during LLM streaming** (November 2025). As the LLM generated Python code token by token, the runtime identified complete statements and executed them immediately, using a backward-walking algorithm to find valid execution boundaries in partially-received code.

**Adaptive waiting** (December 2025). Instead of binary timeouts, the agent receives periodic check-ins with elapsed time, context, and any new messages, then *decides* whether to keep waiting, follow up, or escalate. OpenClaw's heartbeat (January 2026) provides a similar pattern.

**Multi-agent meetings** (July 2025, improved December 2025). Multi-agent sessions with shared state, structured communication protocol, and lifecycle management. Claude Code's Agent Teams (February 2026) solves multi-agent coordination through a different approach---independent sessions with a team lead---seven months after Playbooks' initial implementation.

**Forward compatibility** ([blogged December 2025](https://www.runplaybooks.ai/blog/forward-compatibility-hidden-superpower)). The argument that traditional agent frameworks embed workarounds for current LLM limitations, and when better models arrive, those workarounds prevent the system from leveraging new capabilities. Playbooks programs express pure intent, so the same program runs better on a stronger model without modification. The industry has since internalized this principle, and modern agent harnesses try to stay out of the model's way. But the explicit framing of forward compatibility as a named, deliberate property remains valuable: the moment you add too much scaffolding around the LLM, you lose it.

**JIT coding** ([blogged November 2025](https://www.runplaybooks.ai/blog/just-in-time-coding)). The concept that specifications become the primary artifact and code is generated on-demand during execution, then discarded---"the spec is the program, code is just exhaust." Claude Code had been operating this way since its February 2025 launch, and Codex since May 2025. Playbooks named and framed the pattern. It's worth distinguishing from "vibe coding" where the generated code becomes a durable artifact that humans maintain; in JIT coding, the code is ephemeral.

### A Research Direction: PlaybooksLM

One concept and prototype worth documenting, though I did not ship it publicly: PlaybooksLM, a model built specifically to execute natural language programs reliably, emit structured telemetry through special tokens, and provide model-side verifiability. Instead of hoping a general-purpose LLM follows your specification, you train a model whose job is to *execute* specifications---and it emits custom tokens the runtime uses for tracing and execution validation. Everyone in the industry is working on making general-purpose models better at following instructions. The alternative---models whose primary function is reliable execution of structured natural language programs---remains under-explored.

### Timeline

| Capability | Playbooks | Industry |
|---|---|---|
| NL as programming language | June 2022 (experiments); Sep 2024 (v0.1.0); Oct 2025 (blog) | Anthropic Skills: Oct 2025 |
| Agents as classes/methods | Feb 2025 (v0.2.0) | Not widely adopted in LLM agent frameworks |
| VSCode debugging of NL programs | May 2025 (v0.4.0) | MS Agent Inspector: Feb 2026 (code agents) |
| Event-driven triggers | May 2025 (v0.3.0) | AutoGen v0.4: Jan 2025 (system events); Claude Code hooks: early 2026 (lifecycle) |
| PBAsm / Semantic IR | June 2025 (v0.3.5) | Not attempted elsewhere |
| Stack-based context management | June 2025 | Not attmpted elsewhere |
| Multi-agent meetings | July 2025 (v0.6.0) | Partial support in Claude Code Agent Teams: Feb 2026 |
| Incremental streaming execution | Nov 2025 (v0.7.0) | Not adopted elsewhere |
| Adaptive waiting | Dec 2025 (v0.7.3) | OpenClaw heartbeat: Jan 2026 |

## What the Simpler Approach Does Better

It's worth being honest about where the skills/generalist agent approach genuinely surpasses Playbooks.

**Expressiveness over structure.** A Playbook encodes a process. A skill can encode knowledge, process, caveats, unstructured thoughts---whatever. This makes skills more expressive. You can dump context, heuristics, and edge case guidance into a skill in whatever form makes sense. Playbooks requires you to think in terms of steps and control flow. The cost of skills' expressiveness is less verifiability, but for most use cases that tradeoff is worth it.

**Simpler harness.** A skills-supporting agent harness and the Playbooks runtime are both specialized runtimes in today's terms. What's different is that without a compilation step or heavy process management, skills-supporting harnesses are much easier to build. That's why there are dozens of skills-capable harnesses and only one Playbooks runtime.

**Ecosystem momentum.** Anthropic backing skills as a first-class concept, combined with the broader industry moving toward agentic patterns, created network effects that a solo research project couldn't match. The best specification format is the one people actually use.

**Simpler mental model.** "Write whatever you want and the agent follows it" is immediately understandable. Playbooks' authoring is also simple---it's just markdown with minimal structure---but the compilation model and execution validation underneath add conceptual weight that skills avoids entirely. The sophistication of the runtime leaked into how people perceived the authoring experience, even when it shouldn't have.

**Graceful degradation.** Because a skill is free-form guidance rather than a formal program, when it doesn't work perfectly the agent degrades naturally. When a Playbooks program hits an execution validation error, it can halt. Strictness is a virtue for enterprise reliability but a liability for developer experience. Skills bet that model improvement will close the reliability gap; Playbooks engineered around it.

**Forward compatibility (ironically).** Because skills have less scaffolding, they benefit more from model improvement. That's Playbooks' own principle working against it.

## Reflections

Building Playbooks taught me that being right about the direction isn't enough. You also need to be right about the timing, the constraints, and the level of abstraction.

Playbooks made a bet that enterprise use would require reliable execution. It was built when LLMs were not reliable enough to execute arbitrary instructions with reasonable consistency. The design demanded compilation, execution validation, and formal semantics because without them, nothing worked well enough to trust. Skills started in a different era---LLMs were far more capable by late 2025, and the design constraints were different.

The 79 stars tell their own story. I thought being technically right would matter more than it did. Even before skills existed, the compilation and runtime complexity made Playbooks hard to adopt. The ideas may have been sound, but the packaging was too heavy. The industry wanted something you could drop into a markdown file and have it work. Playbooks required understanding what was happening underneath, and most developers---reasonably---didn't want to.

I thought the industry would reject an unreliable solution. Here we are in April 2026, and the reliable solution is the niche project with 79 stars. What skills bet on, correctly, is that by the time there's serious enterprise adoption, LLMs will be reliable enough and the ecosystem will have built mechanisms to guardrail agents. The ceiling on automatable complexity keeps rising. Skills is riding that curve rather than engineering around it.

Playbooks is correct that natural language should be the programming language for AI agents. It is correct about context management, adaptive waiting, forward compatibility, and multi-agent coordination. But it put complexity in the specification language and runtime when the simpler move was to put complexity in the model itself and keep the specification layer dead simple. As models get better, the skills approach gets better for free. That's the very forward compatibility argument that Playbooks championed, working against it.

The strongest argument for Playbooks' architecture was also the argument for why a simpler approach would eventually win. I think that's a lesson worth internalizing for anyone building infrastructure around rapidly improving AI: every piece of scaffolding you add is a bet that the model won't get good enough to make it unnecessary. Sometimes that bet is correct. Often it isn't.

The Playbooks repository will remain available on GitHub as a reference. The documentation and blog posts at [runplaybooks.ai](https://www.runplaybooks.ai) will stay up for anyone interested in the ideas.

## Thank You

Playbooks has been largely a solo project, but it didn't happen in isolation. I want to think everyone who tried Playbooks and gave me important feedback. And to those who starred the repo: you kept me going. An open-source research project with no corporate backing lives on attention and curiosity, and you provided both.

Research projects succeed not by becoming permanent, but by pushing ideas forward.

---

*Playbooks is a semantic programming system for AI agents featuring a natural language programming language, semantic intermediate representation (PBAsm), and execution runtime. It was open-sourced in September 2024 and actively developed through February 2026.*

*[GitHub](https://github.com/playbooks-ai/playbooks) | [Documentation](https://docs.runplaybooks.ai) | [Blog](https://www.runplaybooks.ai/blog)*
