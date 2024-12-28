# ModifierAgent

## ModifyValue($value)

### Trigger
When the checker agent asks to modify the value

### Steps
- Increment $value
- Ask checker agent to check $value

====

# CheckerAgent

## CheckValue($value)

### Trigger
When the modifier agent asks to check the value

### Steps
- If $value is less than 10, ask modifier agent to modify the value
- Otherwise
  - Tell user that we are done

====

# MainAgent

## Run

### Trigger
When agent starts

### Steps
- Ask modifier agent to modify the value 4