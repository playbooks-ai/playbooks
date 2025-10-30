# Artifacts test

```python
@playbook
def GenerateRandomString():
  import random
  import string
  return ''.join(random.choices(string.ascii_letters, k=1000))
```

## Main
### Triggers
- At the beginning
### Steps
- Get $first_four from PB1
- Tell user the $first_four
- Get $last_four from PB2
- Tell user the $last_four
- Exit program

## PB1
### Steps
- Generate $random_string
- Return first 4 letters from the string

## PB2
### Steps
- Return one dictionary word you see in the already generated random string, otherwise 'None'