# ConditionalVars

## Main
### Triggers
- At the beginning

### Steps
- x is 10
- ask user for a number and store in $usernum
- if $usernum is greater than 5:
  - status is "high"
  - multiplier is 2
- else:
  - status is "low"  
  - multiplier is 1
- result is x * multiplier
- say the status is {status} and result is {result}
- End program
