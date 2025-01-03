import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Playground from '../Playground/Playground';

// Mock the Editor component
jest.mock('../Playground/Editor', () => {
  return function MockEditor({
    initialValue,
    onChange,
  }: {
    initialValue: string;
    onChange?: (value: string) => void;
  }) {
    return (
      <textarea
        data-testid="mock-editor"
        value={initialValue}
        onChange={e => onChange?.(e.target.value)}
      />
    );
  };
});

// Mock fetch
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe('Playground', () => {
  beforeEach(() => {
    mockFetch.mockClear();
  });

  it('loads example playbook on mount', async () => {
    const exampleContent = 'Example playbook content';
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ content: exampleContent }),
    });

    render(<Playground />);

    await waitFor(() => {
      const editor = screen.getByTestId('mock-editor');
      expect(editor).toHaveValue(exampleContent);
    });
  });

  it('handles example playbook loading error', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    render(<Playground />);

    await waitFor(() => {
      expect(screen.getByText(/Error loading example: Network error/)).toBeInTheDocument();
    });
  });

  it('runs playbook when run button is clicked', async () => {
    // Mock successful example load
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ content: 'Example content' }),
    });

    // Mock successful playbook run
    const runResponse = new Response('Playbook result', {
      headers: { 'content-type': 'text/plain' },
    });
    mockFetch.mockResolvedValueOnce(runResponse);

    render(<Playground />);

    // Wait for example to load
    await waitFor(() => {
      expect(screen.getByTestId('mock-editor')).toBeInTheDocument();
    });

    // Click run button
    const runButton = screen.getByRole('button', { name: /run/i });
    fireEvent.click(runButton);

    // Verify fetch was called with correct parameters
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringMatching(/\/api\/run-playbook$/),
        expect.objectContaining({
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'text/event-stream',
          },
          credentials: 'include',
          body: expect.any(String),
        })
      );
    });
  });
});
