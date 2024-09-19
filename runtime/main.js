import { LLM } from "./llm.js";
import { createSystemPrompt, loadPlaybooks } from "./playbook.js";

class PlaybookRuntime {
  constructor(
    projectPath,
    model = process.env.LLM_MODEL || "anthropic/claude-3-sonnet-20240229"
  ) {
    this.llm = new LLM(model);
    const [playbooks, config] = loadPlaybooks(projectPath);
    this.systemPrompt = createSystemPrompt(playbooks, config);
    this.session = null;
  }

  startConversation() {
    this.session = this.llm.createChatSession(this.systemPrompt);
  }

  async chat(message, onContent) {
    if (!this.session) {
      this.startConversation();
    }
    return await this.llm.chat(this.session, message, onContent);
  }
}

export default PlaybookRuntime;
