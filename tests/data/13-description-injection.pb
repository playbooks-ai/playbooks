# TestAgent

## Test playbook
execution_mode: raw
{Loadfile("tests/data/13-description-injection-story.txt", silent=True)}
{Loadfile("tests/data/13-description-injection-instructions.txt", inline=True, silent=True)}
Give the one word answer only, nothing else.
Answer: 

## Main

### Trigger
- When program starts

### Steps
- Run test playbook
- End program