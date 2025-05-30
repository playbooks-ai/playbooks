# Simple NL Calculator
This program demonstrates playbooks framework capabilities - NL-to-Python function calls and implicit state for parameters and results.

```python
import math
@playbook(triggers=["When you want to apply magic operator to a number"])
async def magic_operator(input: str) -> float:
  input_num = float(input)
  return input_num * math.sin(input_num)
```

## DoMagic
### Triggers
- When the program starts
### Steps
- $input = Ask user for a number between 1 and 10
- apply magic operator on $input
- Tell user the result
- End program