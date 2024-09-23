"use client";

import Editor from "@monaco-editor/react";
import React, { useState } from "react";

const PlaybookEditor: React.FC<{ runPlaybook: (code: string) => void }> = ({
  runPlaybook,
}) => {
  const [code, setCode] = useState(`# HelloWorld

## Trigger
When the user starts a conversation or asks for a greeting.

## Steps
- Greet the user with a friendly "Hello, World!" message.
- Give one-line explanation that this is a demonstration of a simple Hello World playbook.
- Say goodbye to the user.

## Notes
- If the user asks about capabilities beyond this simple playbook, explain that this is a basic example and suggest they explore more complex playbooks for advanced features.
- Remember to relate responses back to the concept of Hello World or playbooks when appropriate.`);

  const handleEditorChange = (value: string | undefined) => {
    if (value) setCode(value);
  };

  return (
    <div className="flex flex-col items-center justify-center h-full">
      <Editor
        defaultLanguage="markdown"
        value={code}
        onChange={handleEditorChange}
        theme="vs-light" // Available themes: "vs-light", "vs-dark", "hc-black", "hc-light"
        options={{
          wordWrap: "on",
          fontSize: 16,
          scrollBeyondLastLine: false,
          overviewRulerBorder: false,
          scrollbar: {
            vertical: "visible",
            verticalScrollbarSize: 10,
          },
          minimap: { enabled: false },
          lineNumbers: "on",
          lineNumbersMinChars: 3,
          lineDecorationsWidth: 4,
          padding: { top: 10, bottom: 10 },
        }}
        height="100%"
      />
      <div className="flex justify-center">
        <button
          className="mt-4 mb-4 px-4 py-2 bg-blue-500 text-white font-semibold rounded-lg shadow-md hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-opacity-75 transition duration-300 ease-in-out"
          onClick={() => runPlaybook(code)}
        >
          Run playbook
        </button>
      </div>
    </div>
  );
};

export default PlaybookEditor;
