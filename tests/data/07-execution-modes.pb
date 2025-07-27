# MathSolver

```python
@playbook
import math
async def Factorial(a: float):
    return math.factorial(a)

@playbook
async def Exp(a: float):
    return math.exp(a)

@playbook
async def Log(a: float):
    return math.log(a)

@playbook
async def Sin(a: float):
    return math.sin(a)
```

## Main

### Triggers
- At the beginning

### Steps
- Ask the user for a simple math problem that uses Factorial, Exp, Log, and Sin, e.g. "exp(5!)"
- Use Solver to solve the problem
- Give the answer to the user
- Get $joke from Joke()
- Tell $joke to the user
- End program

## Solver($problem)
You are a math solver. You will be given a math problem and you will solve it. Use available playbooks to solve the problem. Go step by step. Return the final answer at the end.

## Joke
execution_mode: raw
Tell me a one-liner joke about math.