# Host

## Main
### Trigger
- When program starts
### Steps
- Ask user for $gross_income
- Ask Tax accountant what the percent $tax_rate would be for the $gross_income
- Calculate $tax_amount
- Tell user the $tax_amount
- End program


```python
@playbook
async def CalculateTax(gross_income, tax_rate):
    """
    Calculate the tax amount based on the gross income and tax rate
    """
    return gross_income * tax_rate / 100
```

# Tax accountant

## Get tax rate($gross_income)
public: true

### Steps
- If $gross_income < 100000
  - return 15%
- Otherwise
  - return 25%

## Tax strategy meeting
meeting: true

### Steps
- When user asks about best retirement plan to save tax
  - Talk about retirement plans