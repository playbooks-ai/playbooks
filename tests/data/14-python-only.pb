# Python-only agent

```python

@playbook(triggers=["At the beginning"])
async def Main():
  await Say("user", "What's your name?")
  agent.state.messages = await WaitForMessage("user")
  await Say("user", f"Received messages: {agent.state.messages}")
  await Say("user", f"Secret code: {await GetSecret()}")
  await EndProgram()

@playbook
async def GetSecret():
  return "OhSoSecret!"
```
