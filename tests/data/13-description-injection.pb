# TestAgent

## Test playbook
execution_mode: raw
{Loadfile("tests/data/13-description-injection-story.txt", silent=True)}
{Loadfile("tests/data/13-description-injection-instructions.txt", inline=True, silent=True)}
Give the one word answer only, nothing else.
Answer: 

## Test2 playbook
Here is a joke: {Joke()}

### Steps
- Remember joke as $jk

## Main

### Trigger
- When program starts

### Steps
- Run test playbook
- Run test2 playbook
- End program

## Joke

### Steps
- Return "Why was the computer cold? It left its Windows open."