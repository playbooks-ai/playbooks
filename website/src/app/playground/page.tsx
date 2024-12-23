'use client';

import { useState, useEffect } from 'react';
import Editor from '@/components/Playground/Editor';

const defaultPlaybook = `# Loading example playbook...`;

export default function PlaygroundPage() {
  const [content, setContent] = useState(defaultPlaybook);
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const loadExample = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/examples/hello.md');
        if (!response.ok) {
          throw new Error('Failed to load example');
        }
        const data = await response.json();
        setContent(data.content);
      } catch (error) {
        console.error('Error loading example:', error);
        setContent('# Error loading example playbook\n' + (error as Error).message);
      }
    };

    loadExample();
  }, []);

  const runPlaybook = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/api/run-playbook', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          content,
        }),
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to run playbook');
      }
      
      const data = await response.json();
      setResult(data.result);
    } catch (error) {
      setResult('Error running playbook: ' + (error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-4xl font-bold mb-8">Playbook Playground</h1>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div>
          <h2 className="text-2xl font-semibold mb-4">Editor</h2>
          <Editor initialValue={content} onChange={setContent} />
          <button
            onClick={runPlaybook}
            disabled={loading}
            className="mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Running...' : 'Run Playbook'}
          </button>
        </div>
        
        <div>
          <h2 className="text-2xl font-semibold mb-4">Output</h2>
          <div className="h-[600px] w-full border border-gray-200 dark:border-gray-800 rounded-lg p-4 bg-gray-50 dark:bg-gray-900 overflow-auto">
            <pre className="whitespace-pre-wrap font-mono text-sm">
              {result || 'Output will appear here...'}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
