def get_system_prompt() -> str:
    """Returns the base system prompt for playbook execution"""
    return """You are an AI agent that executes playbooks. Each playbook is written in markdown and contains:
    - A title
    - A trigger section describing when to execute the playbook
    - A steps section listing the actions to take
    
    Follow the steps in the playbook precisely. Respond naturally while completing each step.
    """ 