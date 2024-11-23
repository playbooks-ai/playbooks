import Anthropic from "@anthropic-ai/sdk";

export class LLM {
  constructor(model) {
    this.model = model;
    this.client = new Anthropic();
  }

  createChatSession(systemPrompt) {
    return {
      system: systemPrompt,
      messages: [],
    };
  }

  async chat(session, message, onContent) {
    session.messages.push({ role: "user", content: message });

    const stream = await this.client.messages.stream({
      model: this.model,
      system: session.system,
      messages: session.messages,
      max_tokens: 1024, // Adjust as needed
    });

    let fullResponse = "";

    for await (const event of stream) {
      if (event.type === "content_block_delta") {
        const content = event.delta.text;
        fullResponse += content;
        if (onContent) {
          onContent(content);
        }
      }
    }

    const finalMessage = await stream.finalMessage();
    session.messages.push({ role: "assistant", content: fullResponse });
    return fullResponse;
  }
}

// module.exports = { LLM };
