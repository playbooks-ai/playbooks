"use client";

import MessageList from "@/components/MessageList";
import UserInput from "@/components/UserInput";
import { Message } from "@/types";
import { handleChatCompletion } from "@/utils/chatUtils";
import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";

type ChatWidgetProps = object;

interface ChatWidgetRef {
  runPlaybook: (code: string) => void;
}

const beginConversation = "Begin";

const ChatWidget = forwardRef<ChatWidgetRef, ChatWidgetProps>((props, ref) => {
  const [playbook, setPlaybook] = useState<string>("");

  useImperativeHandle(ref, () => ({
    runPlaybook: (code: string) => {
      // Clear the current conversation messages
      setMessages([]);
      console.log("Running playbook with code:", code);
      setPlaybook(code);
      handleSubmit(beginConversation, code);
    },
  }));

  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages, isStreaming]);

  const handleSubmit = async (input: string, pb: string) => {
    if (!input.trim()) return;
    if (!pb) {
      pb = playbook;
    }

    console.log("Messages:", messages);
    console.log("Playbook:", pb);
    console.log("Input:", input);

    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setIsStreaming(true);

    try {
      await handleChatCompletion(pb, [...messages, userMessage], (chunk) => {
        console.log("Raw chunk:", chunk);
        setMessages((prev) => {
          const newMessages = [...prev];
          if (
            newMessages.length > 0 &&
            newMessages[newMessages.length - 1].role === "assistant"
          ) {
            newMessages[newMessages.length - 1].content = chunk;
          } else {
            newMessages.push({
              role: "assistant",
              content: chunk,
            });
          }
          return newMessages;
        });
      });
    } catch (error) {
      console.error("Error:", error);
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div className="flex flex-col h-full max-w-2xl mx-auto p-4">
      <MessageList
        messages={messages}
        isStreaming={isStreaming}
        messagesEndRef={messagesEndRef}
      />
      <UserInput
        onSubmit={(input: string) => handleSubmit(input, playbook)}
        isStreaming={isStreaming}
      />
    </div>
  );
});

ChatWidget.displayName = "ChatWidget";

export default ChatWidget;
