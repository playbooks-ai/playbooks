# Agent1

```python
@playbook
async def python_a1p1():
    print("Python A1P1")

@playbook(triggers=["When program starts"])
async def python_a1p2():
    print("Python A1P2")

@playbook(triggers=["When AGI arrives"])
async def python_a1p3():
    print("Python A1P3")

@playbook(triggers=["When user asks for refund"])
async def python_a1p4():
    print("Python A1P4")
```

## A1P1
- Say "A1P1"

## A1P2
### Triggers
- At the beginning
### Steps
- Say "A1P2"

## A1P3
### Triggers
- At the beginning
### Steps
- Say "A1P3"

## A1P4
### Triggers
- When user asks for refund
### Steps
- Say "A1P4"
- End program

# Agent2

## A2P1
### Triggers
- At the beginning
### Steps
- Say "A2P1"

## A2P2
### Triggers
- At the beginning
### Steps
- Say "A2P2"
- End program

## A2P3
### Triggers
- When pigs fly
### Steps
- Say "A2P3"

## A2P4
- Welcome the user
