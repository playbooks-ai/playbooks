# Dynamic Report Formatter
This program demonstrates playbooks framework capabilities - NL-to-Python-to-NL function calls.

```python
@playbook
async def generate_report_summary():
  # Assume report_data is gathered here by Python logic
  report_data = {"sales": 1000, "region": "North", "trend": "positive"}
  # Python calls the NL playbook 'FormatSummary', passing the dictionary
  summary = await FormatSummary(report_data)
  await Say(f"Generated Summary: {summary}")
```

## FormatSummary($report_data)
### Steps
- Generate a brief, engaging summary based on the provided $report_data
- return the summary

## Main
### Triggers
- At the beginning
### Steps
- generate_report_summary()
