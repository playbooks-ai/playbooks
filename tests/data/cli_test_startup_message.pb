# TestAgent
Test startup message

## Main
### Triggers
- At the beginning
### Steps
- If $startup_message is available
    - Say(user, "Received: {$startup_message}")
- Otherwise
    - Say(user, "No startup_message")
- End program

