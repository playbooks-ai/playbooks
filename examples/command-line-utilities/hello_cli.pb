#!/usr/bin/env playbooks-shebang
# GreetingGenerator
Simple CLI utility that generates greetings

## Main($name)
cli_entry: true
### Triggers
- At the beginning
### Steps
- Generate a friendly greeting for $name
- If $startup_message is available, incorporate that style/instruction into the greeting
- Say(user, Output the greeting)
- End program

