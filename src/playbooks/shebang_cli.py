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


def main():
    """Main entry point for shebang execution.

    This function reconstructs sys.argv to make it appear as if the user
    called 'playbooks run <script_path> <args...>' and then delegates to
    the main CLI.

    When a shebang script is executed (e.g., ./script.pb), the system runs:
        /usr/bin/env pb ./script.pb <args>
    So sys.argv contains:
        sys.argv[0] = path to pb executable
        sys.argv[1] = path to the .pb script file
        sys.argv[2:] = user arguments
    """
    # sys.argv[1] is the path to the playbook file being executed
    if len(sys.argv) < 2:
        print("Error: No playbook file specified", file=sys.stderr)
        sys.exit(1)

    script_path = sys.argv[1]

    # sys.argv[2:] contains the arguments passed by the user
    user_args = sys.argv[2:]

    # Reconstruct sys.argv to look like: ['playbooks', 'run', '<script>', <user_args>]
    sys.argv = ["playbooks", "run", script_path] + user_args

    # Delegate to the main CLI
    from playbooks.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
