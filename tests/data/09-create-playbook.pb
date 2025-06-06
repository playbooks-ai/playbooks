# Test creating a playbook

## Begin
### Triggers
- At the beginning

### Steps
- Ask user for a task
- Create a playbook for the task
- Show playbook to user


## CreatePlaybook($task)
This is a specialized playbook that creates a new playbook to execute given $task.
<playbook_structure>
Each playbook is written as markdown.
- H2 tags define a playbook, e.g. `## MyPlaybook`
- Playbook description is written immediatelly below the ## line
- H3 named Steps has a nested markdown list that gives step by step instructions to execute the task, one instruction on each line
- Steps can set and use $variables, call other playbooks like MyPlaybook($name, 100)

### Steps
- Think deeply about the $task
- While there is any ambiguity in the task definition
  - Engage in a conversation with the user to get the task clarified
- Write a precise and detailed task definition as $precise_task
- Decompose $precise_task into a list of 1 to 7 $subtasks:list
- For each $subtask
  - List steps to execute $subtask
- Write a $playbook:str with steps for all subtasks
- Return $playbook