"use client";

import MessageList from "@/components/MessageList";
import UserInput from "@/components/UserInput";
import { Message } from "@/types";
import { handleChatCompletion } from "@/utils/chatUtils";
import React, { useEffect, useRef, useState } from "react";

const ChatWidget: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages, isStreaming]);

  const handleSubmit = async (input: string) => {
    if (!input.trim()) return;

    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setIsStreaming(true);

    try {
      await handleChatCompletion(
        [...messages, userMessage],
        (assistantMessage) => {
          setMessages((prev) => {
            const newMessages = [...prev];
            if (newMessages[newMessages.length - 1].role === "assistant") {
              newMessages[newMessages.length - 1].content = assistantMessage;
            } else {
              newMessages.push({
                role: "assistant",
                content: assistantMessage,
              });
            }
            return newMessages;
          });
        }
      );
    } catch (error) {
      console.error("Error:", error);
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div className="flex flex-col h-full max-w-2xl mx-auto p-4 bg-white">
      <MessageList
        messages={messages}
        isStreaming={isStreaming}
        messagesEndRef={messagesEndRef}
      />
      <UserInput onSubmit={handleSubmit} isStreaming={isStreaming} />
    </div>
  );
};

export default ChatWidget;
