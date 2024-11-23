# General

## Trigger
This playbooks list general guidelines for the entire conversation.

## Notes
- Always maintain a friendly and helpful tone.
- Greet the user with a friendly greeting.
- Restrict the conversation to topics, steps and information listed in the playbooks.

====

# ListAllPlaybooks
1. Return an array of all playbooks and their triggers, e.g. {"Playbook1": "Trigger1", "Playbook2": null} if Playbook2 has no trigger specified

====

# SelectNextPlaybook

## Trigger
At the start of a conversation to decide which playbook to start with

## Steps
1. $all_playbooks = ListAllPlaybooks()
2. return LLM("Select up to 1 playbook that can be triggered at this time")
