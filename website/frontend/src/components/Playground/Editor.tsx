'use client';

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';

const MonacoEditor = dynamic(() => import('@monaco-editor/react'), {
  ssr: false,
});

interface EditorProps {
  initialValue?: string;
  onChange?: (value: string) => void;
}

export default function Editor({ initialValue = '', onChange }: EditorProps) {
  const [value, setValue] = useState(initialValue);

  useEffect(() => {
    setValue(initialValue);
  }, [initialValue]);

  const handleChange = (newValue: string | undefined) => {
    const updatedValue = newValue || '';
    setValue(updatedValue);
    onChange?.(updatedValue);
  };

  return (
    <div className="monaco-editor-container h-[200px] w-full overflow-hidden rounded-lg border border-gray-200 dark:border-gray-800">
      <MonacoEditor
        height="100%"
        defaultLanguage="yaml"
        theme="vs-dark"
        value={value}
        onChange={handleChange}
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          lineNumbers: 'on',
          roundedSelection: false,
          scrollBeyondLastLine: false,
          readOnly: false,
          automaticLayout: true,
        }}
      />
    </div>
  );
}
