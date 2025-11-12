# ReleaseNotesGenerator
Generates release notes by analyzing git commits between two points

## Main($start, $end)
cli_entry: true

Example release notes - 
    {FilesystemAgent.read_file(file_path="/Users/amolk/work/workspace/playbooks/examples/command-line-utilities/example_release_notes.md")}

### Triggers
- At the beginning
### Steps
- Use shell command "git log --notes $start..$end" with working_dir None and timeout 300 to get full $commit_logs
- Wait for git
- Top level categories to consider are Added, Improved, Changed, Fixed, Remove, Breaking changes. Create a list of categories and subcategories to represent the git logs
- Think how you would write each section in the release notes, identifying if any section would be empty so not included
- Now refer to the example release notes above and note how each bullet point shows why/what/how. Write $release_notes following the same format and approach.
- Say(user, $release_notes)
- End program

---

# FilesystemAgent
Agent providing file system operations through MCP integration.

remote:
  type: mcp
  transport: memory
  url: memory://../deepagents/filesystem_mcp.py

---

# ShellAgent
Agent providing shell command execution through MCP integration.

remote:
  type: mcp
  transport: memory
  url: memory://../deepagents/shell_mcp.py

