import { useState, useRef, useEffect, useCallback } from 'react';

export interface ChatMessage {
  content: string;
  role: string;
}

interface ChatInterfaceProps {
  messages: ChatMessage[];
  onSendMessage: (message: string) => Promise<void>;
  loading: boolean;
}

export default function ChatInterface({ messages, onSendMessage, loading }: ChatInterfaceProps) {
  const [userInput, setUserInput] = useState('');
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    if (chatContainerRef.current) {
      const { scrollHeight, clientHeight, scrollTop } = chatContainerRef.current;
      const isScrolledToBottom = scrollHeight - clientHeight <= scrollTop + 100;

      if (isScrolledToBottom || messages[messages.length - 1]?.role === 'assistant') {
        chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
      }
    }
  }, [messages]);

  useEffect(() => {
    scrollToBottom();
  }, [scrollToBottom]);

  // Focus input when loading finishes
  useEffect(() => {
    if (!loading && messages.length > 0 && messages[messages.length - 1].role === 'assistant') {
      inputRef.current?.focus();
    }
  }, [loading, messages]);

  const handleSend = async () => {
    if (!userInput.trim()) return;
    await onSendMessage(userInput);
    setUserInput('');
  };

  return (
    <div>
      <div
        ref={chatContainerRef}
        className="h-[400px] w-full overflow-auto rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-900"
      >
        <div className="flex flex-col space-y-4">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-2 ${
                  message.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : message.role === 'error'
                      ? 'bg-red-100 text-red-800'
                      : 'bg-gray-200 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                }`}
              >
                <pre className="whitespace-pre-wrap break-words font-mono text-sm">
                  {message.content}
                </pre>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-4 flex items-center space-x-2">
        <input
          ref={inputRef}
          type="text"
          value={userInput}
          onChange={e => setUserInput(e.target.value)}
          onKeyPress={e => e.key === 'Enter' && handleSend()}
          placeholder="Type your message..."
          className="flex-1 rounded-lg border border-gray-300 p-2 dark:border-gray-700 dark:bg-gray-800"
          disabled={loading}
        />
        <button
          onClick={handleSend}
          disabled={loading}
          className="rounded-lg bg-blue-600 px-6 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  );
}
