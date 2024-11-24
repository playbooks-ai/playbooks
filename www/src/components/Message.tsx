import { Message as MessageType } from "@/types";
import { markdownComponents } from "@/utils/markdownComponents";
import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Spinner from "./Spinner";

interface MessageProps {
  message: MessageType;
  isStreaming: boolean;
}

const Message: React.FC<MessageProps> = ({ message, isStreaming }) => {
  return (
    <div
      className={`p-2 ${
        message.role === "user"
          ? "bg-blue-100 rounded-lg ml-auto max-w-[80%]"
          : "w-full"
      }`}
    >
      {message.role === "user" ? (
        message.content
      ) : (
        <pre style={{ "white-space": "pre-wrap" }}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={markdownComponents}
          >
            {message.content}
          </ReactMarkdown>
        </pre>
      )}
      {isStreaming && <Spinner />}
    </div>
  );
};

export default Message;
