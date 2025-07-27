# Example program

```python
@playbook(triggers=["When user provides a PIN"])
async def Validation1(pin: str) -> bool:
  while len(pin) != 4 or not pin.isdigit():
    await Say("user","Sorry, that's not a valid PIN. Please try again.")
    messages = await WaitForMessage("human")
    pin = messages[0].content
  agent.state.variables["$pin"] = pin
  return pin
```

## Main
### Triggers
- At the beginning
### Steps
- Ask user for a $pin
- Ask user for $email
- $x = 10
- Load user account
- $x = $x * 2
- Tell the user their account balance
- Exit program

## LoadAccount($email, $pin)
### Steps
- Return {"balance": 8999}

## Validation2
Validates provided email. Email address must conform to addr-spec in Section 3.4 of RFC 5322:
  addr-spec       =   local-part "@" domain

  local-part      =   dot-atom / quoted-string / obs-local-part

  domain          =   dot-atom / domain-literal / obs-domain

  domain-literal  =   [CFWS] "[" *([FWS] dtext) [FWS] "]" [CFWS]

  dtext           =   %d33-90 /          ; Printable US-ASCII
                      %d94-126 /         ;  characters not including
                      obs-dtext          ;  "[", "]", or "\"
### Triggers
- When user provides an email
### Steps
- While $email is not valid
  - Tell user email is not valid and ask for email again
  - If the user gives up
    - Apologize and end the conversation
- Return email

## TooBig
### Triggers
- When $x > 15
### Steps
- Tell user $x is too big
