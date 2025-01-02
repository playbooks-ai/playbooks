import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import Editor from '../Playground/Editor';

jest.mock('@monaco-editor/react', () => {
  const FakeEditor = jest.fn(props => {
    return (
      <textarea
        data-testid="monaco-editor"
        data-auto={props.wrapperClassName}
        onChange={e => props.onChange(e.target.value)}
        value={props.value}
      ></textarea>
    );
  });
  return FakeEditor;
});

describe('Editor', () => {
  it('renders with initial value', async () => {
    const initialValue = 'test content';
    render(<Editor initialValue={initialValue} />);

    const editor = await waitFor(() => screen.getByTestId('monaco-editor'));
    expect(editor).toHaveValue(initialValue);
  });

  it('calls onChange when content changes', async () => {
    const onChange = jest.fn();
    render(<Editor onChange={onChange} />);

    const editor = await waitFor(() => screen.getByTestId('monaco-editor'));
    fireEvent.change(editor, { target: { value: 'new content' } });
    expect(onChange).toHaveBeenCalledWith('new content');
  });

  it('updates value when initialValue prop changes', async () => {
    const { rerender } = render(<Editor initialValue="initial" />);

    const editor = await waitFor(() => screen.getByTestId('monaco-editor'));
    expect(editor).toHaveValue('initial');

    rerender(<Editor initialValue="updated" />);
    expect(editor).toHaveValue('updated');
  });
});
