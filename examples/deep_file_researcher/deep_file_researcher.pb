# Deep File Researcher

A conversational AI agent that answers user queries by researching and reading contents from a specified directory of markdown files. The agent uses intelligent file discovery, table of contents analysis, and selective content loading to provide accurate and contextually relevant answers.

The agent follows a systematic research pattern:
1. Perform recursive directory listing to discover all markdown files
2. Extract and analyze table of contents from candidate files
3. Select relevant sections based on user query
4. Read specific line ranges or full file content as needed
5. Synthesize findings into a comprehensive answer

## Main
Research a user's question by systematically exploring the file directory.

When user says goodbye, respond appropriately and exit

### Triggers
- When program starts

### Steps
- Welcome user and ask them to specify the folder path containing their markdown files to research
- Get $folder_path from user
- Call FileSystemAgent.validate_directory
- If folder validation fails, ask user to provide a valid folder path and try again; gracefully exit if user gives up
- Tell user the folder is ready, list number of markdown files and ask what they'd like to know from the documentation
- While conversation is ongoing
  - Wait for $user_message from user
  - If user message is chitchat (casual conversation, greetings, thanks, etc.)
    - Reply conversationally without doing research
  - Otherwise
    - Think deeply if we already have relevant information loaded
    - If relevant information is already loaded
      - Answer the question precisely using the loaded information
    - Otherwise
      - Research the question
      - If research was unsuccessful
        - Apologize to user
- End program

## ResearchQuestion($user_message, $folder_path)
Find and read relevant file sections to respond to user message.

### Steps
- Initialize $loop_count to 0
- Initialize $max_loops to 3
- While $loop_count < $max_loops
  - Increment $loop_count
  - Think about what information is still missing and would be needed to answer to user
  - Find $relevant_sections
  - If any relevant section were identified
    - Queue calls to the relevant sections using filesystem agent's read_file_range playbook
    - Wait for the calls to return
  - Think about whether previous + newly loaded information is sufficient to respond to user
  - If yes
    - Respond to user with a comprehensive $answer based on the loaded file content; Include specific citations with file names and line number ranges
    - Return $answer

- Return "Information not found"

## Find relevant sections

### Steps
- If not already loaded, load file hierarchy from FileSystemAgent
- List up to 5 candidate files that may contain information we are looking for
- Queue calls to Extract table of contents for each candidate file
- From all loaded table of contents, identify up to 5 $relevant_sections
- Return $relevant_sections

---

# FileSystemAgent
Agent providing readonly file system operations through MCP integration.

remote:
  type: mcp
  transport: streamable-http
  url: http://127.0.0.1:8888/mcp

