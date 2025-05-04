---
title: "Multi-agent program"
author: "Playbooks AI"
---

# FirstAgent
This is a test agent

```python
import math

@playbook(triggers=["When you need to compute square root"], export=True)
async def A(num: float) -> float:
  return math.sqrt(num)
```

## X($num=10)
### Triggers
- When program starts
### Steps
- Tell user about Canada's secret
- get population of India from the country facts agent
- return $num * population of India * 2


# Country info
This agent returns interesting info about a country

```python
from typing import List

@playbook(export=True)
async def GetLengthOfCountry(country: str):
  return len(country)
```
## LocalPB
- Say hello

## export: GetCountryPopulation($country)
- Compute the square root of the length of $country
- Return the population of $country

## export:GetCountrySecret($country)
### Triggers
- When you need to get a secret about a country
### Steps
- Return an unusual historical fact about $country


