import { Message } from "@/types";

export const handleChatCompletion = async (
  playbook: string,
  messages: Message[],
  onUpdate: (assistantMessage: string) => void
) => {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, playbook }),
  });

  if (!response.ok) throw new Error("Network response was not ok");

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No reader available");

  const decoder = new TextDecoder();
  let assistantMessage = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value, { stream: true });
    assistantMessage += text;
    onUpdate(assistantMessage);
  }
};
