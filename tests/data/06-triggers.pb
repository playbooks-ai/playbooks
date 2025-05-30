# Example program

```python
@playbook(triggers=["When user provides a PIN"])
async def Validation1(pin: str) -> bool:
  while len(pin) != 4 or not pin.isdigit():
    await Say("Sorry, that's not a valid PIN. Please try again.")
    pin = await WaitForMessage("human")
  agent.state.variables["pin"] = pin
  return pin
```

## Main
### Triggers
- At the beginning
### Steps
- Ask user for a PIN
- Ask usre for email
- $x = 10
- Load user account
- $x = $x * 2
- Tell the user their account balance

## LoadAccount($email, $pin)
### Steps
- Return {"balance": 8999}

## Validation2
### Triggers
- When user provides an email
### Steps
- While email is not valid
  - Tell user email is not valid and ask for email again
  - If the user gives up
    - Apologize and end the conversation
- Return email

## TooBig
### Triggers
- When $x > 15
### Steps
- Tell user $x is too big
