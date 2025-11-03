#!/usr/bin/env python
"""Entry point for running playbooks as a module.

This allows running the CLI with: python -m playbooks
"""

from .cli import main

if __name__ == "__main__":
    main()
