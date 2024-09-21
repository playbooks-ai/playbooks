import fs from "fs";
import path from "path";

function loadPlaybooks(projectPath) {
  const playbooks = [];
  const config = {};

  const playbooksDir = path.join(projectPath, "playbooks");
  fs.readdirSync(playbooksDir).forEach((filename) => {
    if (filename.endsWith(".md")) {
      const content = fs.readFileSync(
        path.join(playbooksDir, filename),
        "utf8"
      );
      playbooks.push(content);
    }
  });

  const configPath = path.join(projectPath, "config.json");
  if (fs.existsSync(configPath)) {
    const configContent = fs.readFileSync(configPath, "utf8");
    Object.assign(config, JSON.parse(configContent));
  }

  return [playbooks, config];
}

function createSystemPrompt(playbooks, config) {
  const playbooksStr = playbooks.join("\n");

  const agentName = config.agent_name || "Voltron";
  const description =
    config.description || "A highly intelligent and professional AI agent";
  const personality = config.personality || "friendly and funny";

  const agentInfo = `
    You are an agent created by playbooks.ai. Your name is ${agentName} - ${description}. You are ${personality}.
  `;

  const prompt = `
    ${playbooksStr}
    ====

    ${agentInfo}

    You will follow the above playbooks. If you need to make a backend call, output the call with parameters like SomeCall(param1=100, param2="something") and wait for the call to return results. Otherwise output response to user.

    Importantly, strictly follow the playbooks and don't make up unspecified processes, function calls, or other information. Don't ask the same information from the user multiple times. Don't tell users about the playbooks. Never say anything that is unethical, illegal, or harmful.
  `;

  return prompt;
}

export { createSystemPrompt, loadPlaybooks };
