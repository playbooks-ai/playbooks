# Semantic CLI Utilities

Playbooks programs can run as first-class command-line utilities with automatic argument parsing, natural language control, and clean Unix-style output.

## Overview

Turn your Playbooks into semantic command-line tools that:
- Accept command-line arguments with auto-generated help
- Process piped input from stdin
- Accept natural language instructions via `--message`
- Output clean results to stdout for piping
- Return proper exit codes for automation

## Quick Start

### Example 1: Simple Greeting Generator

Create `hello.pb`:

```markdown
# GreetingGenerator
Simple CLI utility that generates greetings

## Main($name)
cli_entry: true
### Triggers
- At the beginning
### Steps
- Generate a friendly greeting for $name
- If $startup_message is available, incorporate that style/instruction into the greeting
- Say(user, Output the greeting)
- End program
```

Run it:

```bash
# Basic usage
$ playbooks run hello.pb --name "Alice"
Hello, Alice! Welcome!

# With style instruction
$ playbooks run hello.pb --name "Bob" --message "make it formal"
Greetings, Bob. We are delighted to extend our warmest regards...

# Show auto-generated help
$ playbooks run hello.pb --help
```

### Example 2: Text Summarizer with stdin

Create `summarize.pb`:

```markdown
# TextSummarizer
Summarizes text input from stdin or --message

## Main
### Triggers
- At the beginning
### Steps
- If $startup_message is available
    - Say(user, Generate a concise summary of $startup_message in 2-3 sentences)
- Otherwise
    - Say(user, "No input provided. Use --message or pipe text to stdin")
- End program
```

Run it:

```bash
# Pipe from file
$ cat article.txt | playbooks run summarize.pb
<summary output>

# Pipe with style instruction
$ cat article.txt | playbooks run summarize.pb --message "use pirate language"
Ahoy, matey! <pirate summary>

# Direct message
$ playbooks run summarize.pb --message "Your text here..."
<summary>
```

## How It Works

### 1. Define CLI Entry Point

Mark a BGN playbook with `cli_entry: true`:

```markdown
## Main($arg1, $arg2)
cli_entry: true
### Triggers
- At the beginning
```

**Entry point selection:**
- Explicit: Playbook marked with `cli_entry: true`
- Fallback: First BGN playbook if no explicit marker
- Error: Multiple `cli_entry: true` markers

### 2. Define Parameters

Use playbook signatures to define CLI arguments:

**Markdown playbooks:**
```markdown
## Main($start, $end)
```

**Python playbooks:**
```python
@playbook
async def Main(start: str, end: str = "HEAD"):
    # ...
```

Parameters are automatically:
- Added to argparse
- Shown in `--help`
- Passed to BGN playbook as kwargs

### 3. Access stdin and --message

The `$startup_message` variable is automatically set from:

- **stdin only**: Contains piped input
- **--message only**: Contains message text
- **Both**: `f"{stdin}\n\nMessage: {message}"`
- **Auto-Artifact**: Content >500 chars promoted to Artifact and pre-loaded

```markdown
## Main($file)
### Steps
- Process $file
- If $startup_message is available, use as additional instruction
- Output results
```

## Unix Stream Separation

Playbooks uses proper stdout/stderr separation:

**stdout (FD 1):** Agent output only
- Content from `Say("user", ...)`
- Clean, pipeable data

**stderr (FD 2):** All diagnostics
- Version banner
- Compilation logs  
- Agent name prefixes: `[Agent(1000) → User]`
- Framework messages

### Benefits

```bash
# Terminal: See everything
$ playbooks run script.pb --args
[GreetingGenerator(1000) → User]    # stderr (visible)
Hello, Alice!                       # stdout (visible)

# Pipe: Only stdout captured, diagnostics still visible on terminal
$ playbooks run script.pb --args > output.txt
[GreetingGenerator(1000) → User]    # stderr (still shown on terminal!)
# output.txt contains: "Hello, Alice!"

# Completely silent
$ playbooks run script.pb --args --quiet 2>/dev/null

# Save streams separately
$ playbooks run script.pb > output.txt 2> debug.log
```

## Flags

All playbooks support these flags:

- `--message TEXT` - Natural language instruction to the agent
- `--quiet` - Suppress framework logs (only affects stderr verbosity)
- `--non-interactive` - Fail if interactive input required (for CI/CD)
- `--snoop` - Show agent-to-agent messages (multi-agent debugging)

## Complete Examples

### Example 1: hello_cli.pb

Simple greeting generator with style control.

```markdown
# GreetingGenerator
Simple CLI utility that generates greetings

## Main($name)
cli_entry: true
### Triggers
- At the beginning
### Steps
- Generate a friendly greeting for $name
- If $startup_message is available, incorporate that style/instruction into the greeting
- Say(user, Output the greeting)
- End program
```

**Usage:**
```bash
# Basic
playbooks run hello_cli.pb --name "Alice"

# Formal style
playbooks run hello_cli.pb --name "Bob" --message "formal style"

# Pirate style from stdin
echo "pirate style" | playbooks run hello_cli.pb --name "Captain"

# Clean output to file
playbooks run hello_cli.pb --name "Dave" > greeting.txt

# Completely silent
playbooks run hello_cli.pb --name "Eve" --quiet 2>/dev/null
```

### Example 2: summarize_text.pb

Text summarization accepting stdin or message.

```markdown
# TextSummarizer
Summarizes text input from stdin or --message

## Main
### Triggers
- At the beginning
### Steps
- If $startup_message is available
    - Say(user, Generate a concise summary of $startup_message in 2-3 sentences)
- Otherwise
    - Say(user, "No input provided. Use --message or pipe text to stdin")
- End program
```

**Usage:**
```bash
# Pipe from file
cat article.txt | playbooks run summarize_text.pb

# Pipe from command
curl https://example.com/article | playbooks run summarize_text.pb

# With style instruction
cat article.txt | playbooks run summarize_text.pb --message "focus on key metrics"

# Large content (auto-promoted to Artifact)
cat 100KB_document.txt | playbooks run summarize_text.pb
```

### Example 3: generate_release_notes.pb

Git commit analyzer with MCP tools (multi-agent).

```markdown
# ReleaseNotesGenerator
Generates release notes by analyzing git commits

## Main($start, $end)
cli_entry: true
### Triggers
- At the beginning
### Steps
- Use shell command "git log --notes $start..$end" to get commit logs
- Analyze commits and categorize (Added, Improved, Fixed, etc.)
- Format release notes in markdown
- Say(user, Output the formatted release notes)
- End program

---

# FilesystemAgent
remote:
  type: mcp
  url: http://127.0.0.1:8000/mcp

# ShellAgent  
remote:
  type: mcp
  url: http://127.0.0.1:8002/mcp
```

**Usage:**
```bash
# Generate release notes
playbooks run generate_release_notes.pb --start v1.0.0 --end HEAD

# With specific styling
playbooks run generate_release_notes.pb --start abc123 --end def456 \
  --message "Focus on breaking changes"

# Clean output for file
playbooks run generate_release_notes.pb --start v1.0.0 --end HEAD \
  --quiet > RELEASE_NOTES.md

# Show help
playbooks run generate_release_notes.pb --help
```

## Unix-Style Composition

Chain utilities using pipes:

```bash
# Multi-stage pipeline
cat article.txt | \
  playbooks run summarize.pb | \
  playbooks run translate.pb --target-language=spanish | \
  playbooks run format.pb > output.md

# With other Unix tools
playbooks run generate_release_notes.pb --start v1.0.0 --end HEAD | \
  grep -i "breaking" | \
  mail -s "Breaking Changes" team@example.com

# Extract and process
git log --oneline | \
  playbooks run analyze_commits.pb --message "find security fixes" | \
  tee commits.txt
```

## Configuration

### Artifact Threshold

Control when content becomes an Artifact in `playbooks.toml`:

```toml
artifact_result_threshold = 500  # Default: 500 chars
```

Small `$startup_message` (<500 chars): Included inline in LLM prompts
Large `$startup_message` (>500 chars): Stored as Artifact, auto-loaded when needed

### Quiet Mode

Suppress framework logs in `playbooks.toml`:

```toml
debug = false  # Reduces logging verbosity
```

Or use CLI flag:
```bash
playbooks run script.pb --quiet  # Suppresses INFO logs to stderr
```

## Advanced Patterns

### Pattern 1: Data Processing Pipeline

```markdown
## Main($input_file, $output_file)
cli_entry: true
### Steps
- Load CSV from $input_file
- If $startup_message has transformation instructions, apply them
- Save to $output_file
- Say(user, "Processed successfully")
```

Usage:
```bash
playbooks run process.pb --input data.csv --output filtered.csv \
  --message "keep rows where age > 18"
```

### Pattern 2: Analysis Tool

```markdown
## Main($data_source)
cli_entry: true
### Steps
- Fetch data from $data_source
- Analyze for patterns
- If $startup_message specifies focus areas, emphasize those
- Generate report
- Say(user, Output formatted report)
```

Usage:
```bash
# From API
playbooks run analyze.pb --data-source "https://api.example.com/metrics"

# With focus
playbooks run analyze.pb --data-source "data.json" \
  --message "focus on security vulnerabilities"
```

### Pattern 3: Content Generator

```markdown
## Main($topic)
cli_entry: true
### Steps
- Research $topic
- If $startup_message provides context or examples, use them
- Generate comprehensive content
- Say(user, Output content)
```

Usage:
```bash
# Basic
playbooks run generate.pb --topic "Machine Learning"

# With examples from stdin
cat examples.txt | playbooks run generate.pb --topic "AI" \
  --message "use these examples as reference"
```

## Exit Codes

Playbooks CLI utilities return standard Unix exit codes:

| Code | Meaning | Use Case |
|------|---------|----------|
| 0 | Success | Normal completion |
| 1 | Execution error | Agent error, LLM failure, exception |
| 2 | Argument error | Invalid CLI arguments (handled by argparse) |
| 3 | Interactive input required | WaitForMessage called in --non-interactive mode |
| 130 | User interrupted | Ctrl+C (SIGINT) |

Example CI/CD usage:

```bash
#!/bin/bash
playbooks run process.pb --input data.csv --non-interactive --quiet
if [ $? -eq 0 ]; then
    echo "Success"
else
    echo "Failed with code $?"
    exit 1
fi
```

## Best Practices

### 1. Use Descriptive Parameters

```markdown
## Main($input_file, $output_format)
```
Better than:
```markdown
## Main($in, $out)
```

### 2. Handle $startup_message Gracefully

```markdown
### Steps
- Process required arguments
- If $startup_message is available, use as additional context
- Generate output
```

### 3. Provide Clear Output

```markdown
### Steps
- Perform analysis
- Say(user, Output results in structured format)
# NOT: Say(user, "Done!") - too vague for piping
```

### 4. Mark Entry Points Explicitly

For complex programs with multiple agents/playbooks:

```markdown
## Main($args)
cli_entry: true  # Explicit marker prevents ambiguity
```

### 5. Use --quiet for Production

```bash
# Development: See diagnostics
playbooks run script.pb --args

# Production: Clean output
playbooks run script.pb --args --quiet > output.txt
```

## Testing Your CLI Utility

```bash
# Test arguments
playbooks run yourscript.pb --arg1 value1 --arg2 value2

# Test stdin
echo "test input" | playbooks run yourscript.pb

# Test message
playbooks run yourscript.pb --required-arg value --message "instruction"

# Test piping
playbooks run yourscript.pb --args > output.txt
cat output.txt  # Should contain only agent output

# Test exit code
playbooks run yourscript.pb --args --quiet 2>/dev/null
echo $?  # Should be 0 on success

# Test help
playbooks run yourscript.pb --help
```

## Troubleshooting

### Issue: "No input provided" when using stdin

**Cause**: stdin isn't being piped
**Solution**: Verify pipe with `cat file.txt | playbooks run ...`

### Issue: Arguments not recognized

**Cause**: Playbook not compiled or no public.json
**Solution**: Let it compile first, then run again

### Issue: Interactive prompt appears in --non-interactive

**Cause**: Playbook calls `WaitForMessage("human")`
**Solution**: Provide all input via --message or remove interactive parts

### Issue: Large stdin causes timeout

**Cause**: Content might be extremely large
**Solution**: Content >500 chars auto-promotes to Artifact - this is normal and efficient

## Comparison with Traditional CLI Tools

### Traditional Approach
```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--name", required=True)
parser.add_argument("--style")
args = parser.parse_args()

if args.style == "formal":
    print(f"Greetings, {args.name}")
elif args.style == "casual":
    print(f"Hey {args.name}!")
# ... many more elif statements ...
```

### Playbooks Approach
```markdown
## Main($name)
### Steps
- Generate appropriate greeting for $name
- If $startup_message has style preferences, apply them
- Say(user, Output greeting)
```

**Benefits:**
- Natural language handles edge cases automatically
- No explicit conditionals for styles
- Adaptable to new instructions without code changes
- Business-readable logic

## Real-World Use Cases

### 1. Git Workflow Automation

```bash
# Generate release notes
playbooks run generate_release_notes.pb --start v1.0.0 --end HEAD > RELEASE.md

# Create changelog entry
git log --since="1 week ago" | \
  playbooks run summarize_commits.pb --message "group by category" > CHANGELOG.md
```

### 2. Content Processing

```bash
# Summarize documents
find docs/ -name "*.md" -exec cat {} \; | \
  playbooks run summarize.pb > summary.txt

# Transform formats
cat data.json | \
  playbooks run convert.pb --target-format csv > data.csv
```

### 3. Data Analysis

```bash
# Analyze logs
cat server.log | \
  playbooks run analyze_errors.pb --message "focus on 500 errors" | \
  tee error_report.txt | \
  mail -s "Server Errors" ops@example.com
```

### 4. CI/CD Integration

```yaml
# .github/workflows/release.yml
- name: Generate Release Notes
  run: |
    playbooks run generate_release_notes.pb \
      --start ${{ github.event.release.tag_name }} \
      --end HEAD \
      --non-interactive \
      --quiet > RELEASE_NOTES.md
```

## Technical Details

### Variable Flow

1. User runs: `cat file.txt | playbooks run script.pb --message "instruction"`
2. CLI detects stdin and --message
3. Creates: `initial_state = {"startup_message": f"{stdin}\n\nMessage: {message}"}`
4. `Playbooks(initial_state=initial_state)` created
5. `Program.initialize()` sets `agent.state.variables["$startup_message"]`
6. If len > 500: Promotes to Artifact and stores for pre-loading
7. `agent.begin()` → `_pre_execute()` → Artifact pre-loaded into call stack
8. BGN playbook executes with `$startup_message` available
9. Both Python and LLM playbooks can access the variable naturally

### Artifact Auto-Promotion

**Small content** (<500 chars):
- Stored as regular variable
- Included inline in state JSON sent to LLM

**Large content** (>500 chars):
- Promoted to Artifact with summary
- Pre-loaded as `ArtifactLLMMessage` in call stack
- Prevents bloating prompts with repetitive large content

Example with 12KB stdin:
```bash
$ cat large_file.md | playbooks run summarize.pb
# Automatically:
# 1. Creates Artifact("$startup_message", summary="...", value=<12KB>)
# 2. Pre-loads as ArtifactLLMMessage in first frame
# 3. LLM sees artifact in context, can reference it
```

### Stream Routing

All Rich Console instances configured with `stderr=True`:
- `src/playbooks/cli.py`
- `src/playbooks/applications/agent_chat.py`
- `src/playbooks/applications/cli_utility.py`
- `src/playbooks/compilation/compiler.py`
- `src/playbooks/infrastructure/user_output.py`
- `src/playbooks/utils/error_utils.py`

Python logging already uses stderr by default.

Agent output uses explicit `sys.stdout.write()` in stream observers.

## API Reference

### Playbooks Class

```python
from playbooks import Playbooks

playbooks = Playbooks(
    program_paths=["script.pb"],
    cli_args={"arg1": "value1"},           # CLI arguments
    initial_state={"startup_message": "..."}, # Initial variables
)
await playbooks.initialize()
await playbooks.program.run_till_exit()
```

### CLI Utility Application

```python
from playbooks.applications import cli_utility

exit_code = await cli_utility.main(
    program_paths=["script.pb"],
    cli_args={"name": "Alice"},
    message="formal style",
    stdin_content="piped content",
    quiet=True,
    non_interactive=False,
)
```

## See Also

- [Playbooks Language Guide](../language/playbooks-language.md) - Full language reference
- [Agent Guide](../guides/agents.md) - Understanding agents
- [Variables and State](../language/variables-and-state.md) - Working with variables
- [Artifacts](../language/artifacts.md) - Understanding artifacts

## Examples

Complete working examples in `examples/command-line-utilities/`:
- `hello_cli.pb` - Simple greeting with parameters
- `summarize_text.pb` - Text summarization from stdin
- `generate_release_notes.pb` - Git analyzer with MCP (multi-agent)

