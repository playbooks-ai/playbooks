---
title: "Playbooks Python Interop"
author: "Playbooks AI"
version: "0.1.0"
date: "2023-06-15"
tags: ["playbooks", "python", "interop", "example"]
application: MultiAgentChat
---

# Interop
startup_mode: standby
This is a simple chat program that demonstrates two-way interop between natural language and python playbooks

```python
import math

@playbook(triggers=["When you need to compute square root"])
async def A(num: float) -> float:
  return math.sqrt(num)

@playbook
async def B(num: float) -> float:
  return math.pow(num, 2)

@playbook
async def AB(num: float) -> float:
  return await A(await B(num))

@playbook
async def CallX(num: float) -> float:
  return await X(num)

@playbook
async def BAXY1(num: float) -> float:
  return await B(await A(await X(num))) * await Y(num)

```

## X($num)
### Steps
- return $num * 2

## Y($num)
### Steps
- return half of $num

## XY($num)
### Steps
- return X(Y($num))

## CallA($num)
### Steps
- return A($num)

## BAXY2($num)
### Steps
- return B(A(X($num))) * Y($num) 
