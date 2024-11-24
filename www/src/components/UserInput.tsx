import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import React, { useState } from "react";

interface UserInputProps {
  onSubmit: (input: string) => void;
  isStreaming: boolean;
}

const UserInput: React.FC<UserInputProps> = ({ onSubmit, isStreaming }) => {
  const [input, setInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(input);
    setInput("");
  };

  return (
    <form onSubmit={handleSubmit} className="flex space-x-2">
      <Input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        className="flex-1 p-2 border rounded-lg"
        placeholder="Type your message..."
        disabled={isStreaming}
      />
      <Button
        type="submit"
        className="bg-blue-500 text-white px-4 py-2 rounded-lg disabled:bg-blue-300"
        disabled={isStreaming}
      >
        {isStreaming ? "Sending..." : "Send"}
      </Button>
    </form>
  );
};

export default UserInput;
