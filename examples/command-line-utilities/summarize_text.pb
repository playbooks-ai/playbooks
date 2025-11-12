# TextSummarizer
Summarizes text input from stdin or --message

## Main
### Triggers
- At the beginning
### Steps
- If $startup_message is available
    - Say(user, Generate a concise summary of $startup_message in 2-3 sentences)
- Otherwise
    - Say(user, "No input provided. Use --message or pipe text to stdin")
- End program

