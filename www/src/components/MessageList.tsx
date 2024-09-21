import Message from "@/components/Message";
import { Message as MessageType } from "@/types";
import React from "react";

interface MessageListProps {
  messages: MessageType[];
  isStreaming: boolean;
  messagesEndRef: React.RefObject<HTMLDivElement>;
}

const MessageList: React.FC<MessageListProps> = ({
  messages,
  isStreaming,
  messagesEndRef,
}) => {
  return (
    <div className="flex-1 overflow-y-auto mb-4 space-y-4">
      {messages.map((message, index) => (
        <Message
          key={index}
          message={message}
          isStreaming={isStreaming && index === messages.length - 1}
        />
      ))}
      <div ref={messagesEndRef} />
    </div>
  );
};

export default MessageList;
