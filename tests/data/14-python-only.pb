# Python-only agent

```python

@playbook(triggers=["At the beginning"])
async def Main():
  Say("user", "What's your name?")
  messages = WaitForMessage("user")
  Say("user", f"Received messages: {messages}")
  Say("user", f"Secret code: {await GetSecret()}")
  Exit()

@playbook
async def GetSecret():
  return "OhSoSecret!"
```
