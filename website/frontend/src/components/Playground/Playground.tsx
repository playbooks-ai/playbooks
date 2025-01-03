'use client';

import { useState, useEffect } from 'react';
import Editor from './Editor';
import { loadExamplePlaybook, runPlaybook, sendChatMessage } from './api';
import ChatInterface, { ChatMessage } from './ChatInterface';

const defaultPlaybook = `Loading example playbook...`;

interface PlaygroundProps {
  className?: string;
}

export default function Playground({ className = '' }: PlaygroundProps) {
  const [content, setContent] = useState(defaultPlaybook);
  const [result, setResult] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadExample = async () => {
      try {
        const exampleContent = await loadExamplePlaybook();
        setContent(exampleContent);
        setError(null);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Unknown error';
        setError(`Error loading example: ${errorMessage}`);
        console.error('Error loading example playbook:', error);
      }
    };
    loadExample();
  }, []);

  return (
    <div className={`${className}`}>
      <div className="grid grid-cols-1 gap-8">
        {error && (
          <div className="text-red-600" role="alert">
            {error}
          </div>
        )}
        <div>
          <h3 className="mb-4 text-2xl font-semibold">This is a playbook</h3>
          <Editor initialValue={content} onChange={setContent} />
          <button
            onClick={async () => {
              setLoading(true);
              try {
                await runPlaybook(content, {
                  onMessageUpdate: messages => setResult(messages),
                  onError: error => console.error('Error running playbook:', error),
                  onDone: () => setLoading(false),
                });
              } catch (error) {
                console.error('Error running playbook:', error);
                setLoading(false);
              }
            }}
            disabled={loading}
            className="float-right mt-4 rounded-lg bg-blue-600 px-6 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Running...' : 'Run Playbook'}
          </button>
        </div>

        <div>
          <h3 className="mb-4 text-2xl font-semibold">
            This is an AI Agent running the above playbook
          </h3>
          <ChatInterface
            messages={result}
            onSendMessage={async message => {
              setLoading(true);
              try {
                await sendChatMessage(message, content, result, {
                  onMessageUpdate: messages => setResult(messages),
                  onError: error => console.error('Error sending message:', error),
                  onDone: () => setLoading(false),
                });
              } catch (error) {
                console.error('Error sending message:', error);
                setLoading(false);
              }
            }}
            loading={loading}
          />
        </div>
      </div>
    </div>
  );
}
