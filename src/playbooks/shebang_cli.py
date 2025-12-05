#!/usr/bin/env python
"""Shebang entry point for direct execution of playbook files.

This module provides the entry point for executing playbook files directly
with a shebang line, allowing usage like:

    #!/usr/bin/env pb

Then the file can be executed directly:
    ./my_script.pb --arg1 value1 --arg2 value2

Instead of:
    playbooks run my_script.pb --arg1 value1 --arg2 value2
"""

import sys
from pathlib import Path


def main():
    """Main entry point for shebang execution.

    This function reconstructs sys.argv to make it appear as if the user
    called 'playbooks run <script_path> <args...>' and then delegates to
    the main CLI.
    """
    # sys.argv[0] is the path to the playbook file being executed
    script_path = sys.argv[0]

    # Resolve to absolute path for clarity
    script_path = str(Path(script_path).resolve())

    # sys.argv[1:] contains the arguments passed by the user
    user_args = sys.argv[1:]

    # Reconstruct sys.argv to look like: ['playbooks', 'run', '<script>', <user_args>]
    sys.argv = ["playbooks", "run", script_path] + user_args

    # Delegate to the main CLI
    from playbooks.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
