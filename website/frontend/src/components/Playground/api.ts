import { ChatMessage } from './types';

const API_URL = process.env.NEXT_PUBLIC_API_URL;

interface StreamProcessor {
  onChunk: (chunk: string) => void;
  onDone?: () => void;
  onError?: (error: Error) => void;
}

async function processStream(response: Response, processor: StreamProcessor) {
  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No reader available');
  }

  let result = '';
  const decoder = new TextDecoder();

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      if (chunk.trim()) {
        result += chunk;
        processor.onChunk(result);
      }
    }
    processor.onDone?.();
  } catch (error) {
    processor.onError?.(error as Error);
  }
}

export async function loadExamplePlaybook(): Promise<string> {
  const response = await fetch(`${API_URL}/api/examples/hello.md`);
  if (!response.ok) {
    throw new Error('Failed to load example playbook');
  }
  const { content } = await response.json();
  return content;
}

export async function runPlaybook(
  content: string,
  {
    onMessageUpdate,
    onError,
    onDone,
  }: {
    onMessageUpdate: (messages: ChatMessage[]) => void;
    onError: (error: Error) => void;
    onDone: () => void;
  }
) {
  try {
    const response = await fetch(`${API_URL}/api/run-playbook`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        content,
        stream: true,
      }),
    });

    if (response.headers.get('content-type')?.includes('text/plain')) {
      await processStream(response, {
        onChunk: assistantResponse => {
          onMessageUpdate([{ role: 'assistant', content: assistantResponse }]);
        },
        onDone,
      });
    } else {
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Failed to run playbook');
      }
      onMessageUpdate([{ role: 'assistant', content: data.message }]);
      onDone();
    }
  } catch (error) {
    onMessageUpdate([{ role: 'error', content: 'Error: ' + (error as Error).message }]);
    onError(error as Error);
  }
}

export async function sendChatMessage(
  message: string,
  content: string,
  previousMessages: ChatMessage[],
  {
    onMessageUpdate,
    onError,
    onDone,
  }: {
    onMessageUpdate: (messages: ChatMessage[]) => void;
    onError: (error: Error) => void;
    onDone: () => void;
  }
) {
  // Add the user's message to the chat history immediately
  const updatedMessages = [...previousMessages, { role: 'user', content: message }];
  onMessageUpdate(updatedMessages);

  try {
    const response = await fetch(`${API_URL}/api/run-playbook`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        content: `${content}\n\nUser: ${message}`,
        stream: true,
      }),
    });

    if (response.headers.get('content-type')?.includes('text/plain')) {
      await processStream(response, {
        onChunk: assistantResponse => {
          onMessageUpdate([...updatedMessages, { role: 'assistant', content: assistantResponse }]);
        },
        onDone,
      });
    } else {
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Failed to send message');
      }
      onMessageUpdate([...updatedMessages, { role: 'assistant', content: data.result }]);
      onDone();
    }
  } catch (error) {
    onMessageUpdate([
      ...updatedMessages,
      { role: 'error', content: 'Error: ' + (error as Error).message },
    ]);
    onError(error as Error);
  }
}
