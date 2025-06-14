---
title: "Multi-agent program"
author: "Playbooks AI"
---

# FirstAgent
This is a test agent

```python
import math

@playbook(triggers=["When you need to compute square root"], public=True)
async def A(num: float) -> float:
  return math.sqrt(num)
```

## X($num=10)
### Triggers
- When program starts
### Steps
- Get Canada's secret
- Tell user about Canada's secret
- get $population of India from the country info agent
- return "{$num} {$population}"


# Country info
This agent returns interesting info about a country

```python
from typing import List

@playbook(public=True)
async def GetLengthOfCountry(country: str):
  return len(country)
```
## LocalPB
### Steps
- Say hello

## GetCountryPopulation($country)
public: true
### Steps
- $population = Compute the square root of the length of $country
- Return $population

## GetCountrySecret($country)
public: true
### Triggers
- When you need to get a secret about a country
### Steps
- Return an unusual historical fact about $country

## Main

### Triggers
- At the beginning

### Steps
- $answer = FirstAgent.A(1024)
- Tell user the $answer
- End program
