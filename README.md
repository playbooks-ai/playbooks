# Playbooks
A framework for creating AI agents using human-readable and LLM-executed playbooks.

## Quick start

It takes just a minute to try out playbooks!
```bash
pip install playbooks
playbooks run examples/hello.md
```

Now write a playbook or two for a simple scenario and try it out. Don't worry, the syntax is quite flexible and forgiving.

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

It all starts with a playbook. Here is an example playbook -

```playbook
# HelloWorld

## Trigger
When the user starts a conversation or asks for a greeting.

## Steps
- Greet the user with a friendly "Hello, World!" message.
- Explain that this is a demonstration of a simple Hello World playbook.
- Say goodbye to the user.

```

## Contributing

Building the playbooks framework will take a villege, so contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 