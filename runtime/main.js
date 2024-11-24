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

  async chat(message, conversationHistory = []) {
    const messages = conversationHistory.map((msg) => ({
      role: msg.role,
      content: msg.content,
    }));

    messages.push({ role: "user", content: message });

    const response = await this.llm.chat(messages);

    return {
      textResponse: response.completion,
      // ...other properties you might want to return
    };
  }
}

export default PlaybookRuntime;
