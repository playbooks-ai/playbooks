# Playbooks.ai Runtime

## Overview
Playbooks.ai Runtime is a Python-based execution environment for AI-powered playbooks.

## Installation
```bash
pip install -r requirements.txt
```

Create a .env file with the following:
```bash
ANTHROPIC_API_KEY=<your_anthropic_api_key>
```

## Usage
Run the CLI with:
```bash
python -m runtime.src.cli --project <path_to_project> [--model <model_name>]
```

- `--project`: Path to the project folder containing playbooks and config.json
- `--model`: (Optional) LLM model to use (default: anthropic/claude-3-sonnet-20240229)

Example:
```bash
cd playbooks.ai
python -m runtime.src.cli --project examples/hello_world
```

## Features
- Execute AI-powered playbooks
- Interactive chat sessions
- Customizable AI model selection

## Contributing
Contributions are welcome! Please refer to CONTRIBUTING.md for guidelines.

## License
[Specify your license here]