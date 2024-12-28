'use client';

import { useState, useEffect } from 'react';
import Editor from './Editor';

const defaultPlaybook = `Loading example playbook...`;
const API_URL = process.env.NEXT_PUBLIC_API_URL;

interface PlaygroundProps {
  className?: string;
}

export default function Playground({ className = '' }: PlaygroundProps) {
  const [content, setContent] = useState(defaultPlaybook);
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);

  const loadExamplePlaybook = async () => {
    try {
      const response = await fetch(`${API_URL}/api/examples/hello.md`);
      if (!response.ok) {
        throw new Error('Failed to load example playbook');
      }
      const { content } = await response.json();
      const text = content;
      setContent(text);
    } catch (error) {
      setResult('Error loading example: ' + (error as Error).message);
    }
  };

  useEffect(() => {
    loadExamplePlaybook();
  }, []);

  const runPlaybook = async () => {
    setLoading(true);
    setResult('');
    try {
      const response = await fetch(`${API_URL}/api/run-playbook`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          content,
          llm_provider: 'anthropic',
          stream: true,
        }),
      });
      
      if (response.headers.get('content-type')?.includes('text/plain')) {
        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('No reader available');
        }

        const decoder = new TextDecoder();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          if (chunk.trim()) {
            setResult(prev => prev + chunk);
          }
        }
      } else {
        const data = await response.json();
        setResult(data.result);
      }
    } catch (error) {
      setResult('Error running playbook: ' + (error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`${className}`}>
      <div className="grid grid-cols-1 gap-8">
        <div>
          <h3 className="text-2xl font-semibold mb-4">This is a playbook</h3>
          <Editor initialValue={content} onChange={setContent} />
          <button
            onClick={runPlaybook}
            disabled={loading}
            className="float-right mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Running...' : 'Run Playbook'}
          </button>
        </div>
        
        <div>
          <h3 className="text-2xl font-semibold mb-4">This is an AI Agent running the above playbook</h3>
          <div className="h-[400px] w-full border border-gray-200 dark:border-gray-800 rounded-lg p-4 bg-gray-50 dark:bg-gray-900 overflow-auto">
            <pre className="whitespace-pre-wrap font-mono text-sm break-words">
              {result || 'Output will appear here...'}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
