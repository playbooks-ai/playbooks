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
  const decoder = new TextDecoder();

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const text = decoder.decode(value);
      const lines = text.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(5).trim();
          if (data === '[DONE]') {
            processor.onDone?.();
            break;
          }
          try {
            const parsed = JSON.parse(data);
            if (parsed.error) {
              processor.onError?.(new Error(parsed.error));
            } else if (parsed.content) {
              processor.onChunk(parsed.content);
            }
          } catch {
            console.warn('Failed to parse SSE data:', data);
          }
        }
      }
    }
  } catch (error) {
    processor.onError?.(error as Error);
  } finally {
    reader.releaseLock();
  }
}

export async function loadExamplePlaybook(): Promise<string> {
  const response = await fetch(`${API_URL}/api/examples/hello.md`, {
    credentials: 'include',
  });
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
        Accept: 'text/event-stream',
      },
      credentials: 'include',
      body: JSON.stringify({
        content,
        stream: true,
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to run playbook');
    }

    if (response.headers.get('content-type')?.includes('text/event-stream')) {
      let accumulatedResponse = '';
      await processStream(response, {
        onChunk: assistantResponse => {
          accumulatedResponse += assistantResponse;
          onMessageUpdate([{ role: 'assistant', content: accumulatedResponse }]);
        },
        onError,
        onDone,
      });
    } else {
      const result = await response.json();
      onMessageUpdate([{ role: 'assistant', content: result.result }]);
      onDone();
    }
  } catch (error) {
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
    const response = await fetch(`${API_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      credentials: 'include',
      body: JSON.stringify({
        message,
        stream: true,
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to send message');
    }

    if (response.headers.get('content-type')?.includes('text/event-stream')) {
      let accumulatedResponse = '';
      await processStream(response, {
        onChunk: assistantResponse => {
          accumulatedResponse += assistantResponse;
          onMessageUpdate([
            ...updatedMessages,
            { role: 'assistant', content: accumulatedResponse },
          ]);
        },
        onError,
        onDone,
      });
    } else {
      const result = await response.json();
      onMessageUpdate([...updatedMessages, { role: 'assistant', content: result.result }]);
      onDone();
    }
  } catch (error) {
    onError(error as Error);
  }
}
