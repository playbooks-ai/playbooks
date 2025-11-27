# TestAgent
Test agent with Python BGN

```python
@playbook(triggers="When program begins")
async def Main(arg1: str, arg2: str = "default"):
    result = f"Got {arg1} and {arg2}"
    await Say("user", result)
    await EndProgram()
```

