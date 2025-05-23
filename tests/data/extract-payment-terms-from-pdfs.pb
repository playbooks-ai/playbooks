# Extract payment terms

```python
import pdfreader

@playbook
async def ProcessFiles():
  files = os.listdir("*.pdf")
  for file in files:
    text = pdfreader.extract_text(file)
    terms = await ExtractPaymentTerms(text)
    print(file, terms)
```

## ExtractPaymentTerms($text)

### Steps
- Find $payment_terms in $text. Payment terms are usually in the last 10% of the document and they contain things like Net 30, 60, 90 days, any late fees, etc.
- return $payment_terms

## Main

### Triggers
- When program starts

### Steps
- ProcessFiles()
- End program
