// Initialize Monaco Editor
require.config({
  paths: {
    vs: "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.30.1/min/vs",
  },
});

let playbookEditor, configEditor;
let ws;

require(["vs/editor/editor.main"], function () {
  playbookEditor = monaco.editor.create(
    document.getElementById("playbook-editor"),
    {
      value:
        '# HelloWorld\n\n## Trigger\nWhen the user starts a conversation or asks for a greeting.\n\n## Steps\n- Greet the user with a friendly "Hello, World!" message.\n- Explain that this is a demonstration of a simple Hello World playbook.\n- Say goodbye to the user.\n\n## Notes\n- If the user asks about capabilities beyond this simple playbook, explain that this is a basic example and suggest they explore more complex playbooks for advanced features.\n- Remember to relate responses back to the concept of Hello World or playbooks when appropriate.',
      language: "markdown",
      theme: "vs-dark",
    }
  );

  configEditor = monaco.editor.create(
    document.getElementById("config-editor"),
    {
      value:
        '{\n  "project_name": "Hello World",\n  "description": "A simple Hello World playbook",\n  "version": "1.0.0"\n}',
      language: "json",
      theme: "vs-dark",
    }
  );
});

// Chat UI
const chatContainer = document.getElementById("chat-messages");
const runButton = document.getElementById("run-button");
const messageInput = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");

runButton.addEventListener("click", runPlaybook);
sendButton.addEventListener("click", sendMessage);
messageInput.addEventListener("keypress", function (e) {
  if (e.key === "Enter") {
    sendMessage();
  }
});

function runPlaybook() {
  const playbookContent = playbookEditor.getValue();
  const configContent = configEditor.getValue();

  fetch("http://localhost:3000/api/playbook/run", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ playbook: playbookContent, config: configContent }),
  })
    .then((response) => response.json())
    .then((data) => {
      addMessage(data, "ai");
    })
    .catch((error) => {
      console.error("Error:", error);
      addMessage("Error executing playbook: " + error.message, "ai");
    });
}

function sendMessage() {
  const message = messageInput.value.trim();
  if (message) {
    addMessage(message, "user");
    ws.send(JSON.stringify({ type: "chat", content: message }));
    messageInput.value = "";
  }
}

function addMessage(content, sender) {
  const messageElement = document.createElement("div");
  messageElement.classList.add("chat-message", `${sender}-message`);
  // Use marked to convert Markdown to HTML, then sanitize with DOMPurify
  messageElement.innerHTML = DOMPurify.sanitize(marked.parse(content));
  chatContainer.appendChild(messageElement);
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

// WebSocket connection
function connectWebSocket() {
  // Use wss:// for secure connections, ws:// for non-secure
  const protocol = window.location.protocol === "https:" ? "wss://" : "ws://";
  const host = window.location.hostname;
  const port = 3000; // Make sure this matches your WebSocket server port

  ws = new WebSocket(`${protocol}${host}:${port}`);

  ws.onmessage = function (event) {
    const message = JSON.parse(event.data);
    addMessage(message.content, message.sender === "ai" ? "ai" : "user");
  };

  ws.onclose = function () {
    console.log("WebSocket connection closed");
    setTimeout(connectWebSocket, 1000);
  };

  ws.onerror = function (error) {
    console.error("WebSocket error:", error);
  };
}

connectWebSocket();
