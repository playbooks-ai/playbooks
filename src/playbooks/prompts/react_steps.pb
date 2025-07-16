### Steps
- Think deeply about the $task to understand requirements and context
- Write down $exit_conditions for the task
- While $exit_conditions are not met
  - Think deeply about current state, the $task and the goals and decide what to do next. You can decide to call a playbook, say something to the user, ask user for information, or take some other action. Precisely follow the playbook instructions.
  - Execute the action you decided on
- If $task could not be completed
  - Return detailed error message
- Otherwise
  - Return results requested by the $task
