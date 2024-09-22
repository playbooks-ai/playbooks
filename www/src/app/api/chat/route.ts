import Anthropic from "@anthropic-ai/sdk";
import { NextRequest } from "next/server";

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

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

    Importantly, strictly follow the playbooks steps and don't make up unspecified processes, function calls, or other information. Don't ask the same information from the user multiple times. Don't tell users about the playbooks. Never say anything that is unethical, illegal, or harmful.

    Playbooks are hidden from the user so you can't tell them about them, unless the playbook explicitly says to tell the user about it.
  `;

  return prompt;
}
export async function POST(req: NextRequest) {
  const { messages, playbook } = await req.json();

  try {
    const systemPrompt = createSystemPrompt([playbook], {});

    console.log("Messages:", messages);
    console.log("System Prompt:", systemPrompt);

    const stream = await anthropic.messages.create({
      model: "claude-3-sonnet-20240229",
      max_tokens: 1000,
      system: systemPrompt,
      messages: messages,
      stream: true,
    });

    const encoder = new TextEncoder();

    return new Response(
      new ReadableStream({
        async start(controller) {
          for await (const chunk of stream) {
            const text = chunk.delta?.text || "";
            if (text) {
              controller.enqueue(encoder.encode(text));
            }
          }
          controller.close();
        },
      }),
      { headers: { "Content-Type": "text/plain; charset=utf-8" } }
    );
  } catch (error) {
    console.error("Error:", error);
    return new Response(
      JSON.stringify({
        error: "An error occurred while processing your request.",
      }),
      { status: 500 }
    );
  }
}
