# Command-Line Utilities with Playbooks

This directory demonstrates how to use Playbooks as semantic command-line utilities.

## Quick Examples

NOTE: You will need to make the examples executable by running `chmod +x <example>`.

### Basic CLI Utility
```bash
# Run with arguments
./hello --name "Alice"

# Clean output to file (only stdout captured)
./hello --name "Bob" > greeting.txt

# Completely silent
./hello --name "Charlie" --quiet 2>/dev/null > greeting.txt
```

### With Natural Language Control
```bash
# Add --message for semantic instructions
./hello --name "Dave" --message "Make it sound formal"

# Pirate style
./hello --name "Eve" --message "Use pirate language"
```

### Unix-Style Piping
```bash
# Pipe stdin to agent
cat example_release_notes.md | ./summarize

# Combine stdin + message
cat example_release_notes.md | ./summarize --message "Produce 3-4 bullet points"

# Chain utilities
cat example_release_notes.md | \
  ./summarize | \
  ./translate --target=spanish
```

## How It Works

### 1. Define CLI Entry Point

Mark your BGN playbook with `cli_entry: true` and parameters:

```markdown
## Main($required_arg, $optional_arg)
cli_entry: true
### Triggers
- At the beginning
### Steps
- Process $required_arg and $optional_arg
- If $startup_message is available (from --message or stdin), use as additional context
- Generate and output results
- Say(user, Output results)
- End program
```

**Note**: `$startup_message` is automatically set from stdin and/or --message flag

### 2. Automatic Argument Detection

Playbooks automatically:
- Detects BGN playbooks with parameters
- Generates argparse configuration from the signature
- Shows auto-generated help with `--help`
- Routes to CLI mode when parameters are provided

### 3. Stream Separation

All Playbooks CLI utilities use proper Unix stream separation:

**stdout (file descriptor 1):**
- Agent output from `Say("user", ...)`
- Clean, pipeable content
- Perfect for chaining with other tools

**stderr (file descriptor 2):**
- Version banner
- Compilation logs
- Agent name prefixes `[Agent(1000) → User]`
- Framework diagnostics

This means you can:
```bash
# See everything on terminal
$ ./script.pb --args

# Pipe clean output, still see diagnostics
$ ./script.pb --args > output.txt

# Suppress diagnostics
$ ./script.pb --args 2>/dev/null

# Save both separately
$ ./script.pb --args > output.txt 2> debug.log
```

## Available Examples

1. **hello_cli.pb** - Simple greeting generator
2. **generate_release_notes.pb** - Git commit analyzer
3. **summarize.pb** - Text summarization with stdin

## Flags

- `--message TEXT` - Natural language instruction
- `--quiet` - Suppress logging (framework stays quiet)
- `--non-interactive` - Fail if input needed (for CI/CD)
- `--snoop` - Show agent-to-agent messages

## Exit Codes

- `0` - Success
- `1` - Execution error
- `2` - Argument error
- `3` - Interactive input required (--non-interactive)
- `130` - User interrupted (Ctrl+C)

For complete examples, see [CLI_UTILITIES_EXAMPLES.md](CLI_UTILITIES_EXAMPLES.md)

