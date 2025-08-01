# Facts about nearby countries
This program prints interesting facts about nearby countries

```python
from typing import List

@playbook
async def process_countries(countries: List[str]):
  # Python loop iterates through the list provided by the NL playbook
  for country in countries:
    # Python calls the NL playbook 'GetCountryFact' for each country
    fact = await GetCountryFact(country)
    await Say("user", f"{country}: {fact}")
```

## GetCountryFact($country)
### Steps
- Return an unusual historical fact about $country

## Main
### Triggers
- At the beginning
### Steps
- Ask user what $country they are from
- If user did not provide a country, engage in a conversation and gently nudge them to provide a country
- List 5 $countries near $country
- Tell the user the nearby $countries
- Inform the user that you will now tell them some interesting facts about each of the countries
- process_countries($countries)
- End program
 