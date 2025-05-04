---
title: "Extract info from PDF files"
author: "Playbooks AI"
version: "0.1.0"
date: "2025-04-13"
tags: ["playbooks", "python", "example"]
application: MultiAgentChat
---
# Extract from files
This program extracts information from PDF files

```python
import json
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

def extract_text_from_pdf(path: str):
    converter = PdfConverter(
        artifact_dict=create_model_dict(),
    )
    rendered = converter(path)
    text, _, images = text_from_rendered(rendered)
    return text

@playbook
async def process_files(path: str):
    """
    Extract information from PDF files
    """
    fileinfo = {}
    for file in files:
        fileinfo["text"] = await extract_text_from_pdf(file)
        fileinfo["metadata"] = await extract_metadata_from_text(fileinfo["text"])

    # save the fileinfo to a json file
    with open("fileinfo.json", "w") as f:
        json.dump(fileinfo, f)

    return fileinfo
```

## extract_metadata_from_text(text)

### Steps
- Extract main $heading from the text
- Summarize the text in a few sentences into $summary
- Clear the text variable
- return a json object with the following keys: heading, summary

## Main
### Triggers
- At the beginning

### Actions
- Ask user for the path to the folder containing the PDF files
- process_files(path)
