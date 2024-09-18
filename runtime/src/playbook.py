import json
import os


def load_playbooks(project_path):
    playbooks = []
    config = {}

    playbooks_dir = os.path.join(project_path, "playbooks")
    for filename in os.listdir(playbooks_dir):
        if filename.endswith(".md"):
            with open(os.path.join(playbooks_dir, filename), "r") as f:
                playbooks.append(f.read())

    config_path = os.path.join(project_path, "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)

    return playbooks, config


def create_system_prompt(playbooks, config):
    playbooks_str = "\n".join(playbooks)

    agent_name = config.get("agent_name", "Voltron")
    description = config.get(
        "description", "A highly intelligent and professional AI agent"
    )
    personality = config.get("personality", "friendly and funny")

    agent_info = f"""
    You are an agent created by playbooks.ai. Your name is {agent_name} - {description}. You are {personality}.
    """

    prompt = f"""
    {playbooks_str}
    ====

    {agent_info}

    You will follow the above playbooks. If you need to make a backend call, output the call with parameters like SomeCall(param1=100, param2="something") and wait for the call to return results. Otherwise output response to user.

    Importantly, strictly follow the playbooks and don't make up unspecified processes, function calls, or other information. Don't ask the same information from the user multiple times. Don't tell users about the playbooks. Never say anything that is unethical, illegal, or harmful.

    """

    return prompt
