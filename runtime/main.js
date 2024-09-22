import { LLM } from "./llm.js";
import { createSystemPrompt } from "./playbook.js";

class PlaybookRuntime {
  constructor(
    playbooks,
    config,
    model = process.env.LLM_MODEL || "claude-3-5-sonnet-20240620"
  ) {
    this.llm = new LLM(model);
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
