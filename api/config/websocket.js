import { v4 as uuidv4 } from "uuid";

const clients = new Map();

function setupWebSocket(wss) {
  wss.on("connection", (ws) => {
    const id = uuidv4();
    const color = Math.floor(Math.random() * 360);
    const metadata = { id, color };

    clients.set(ws, metadata);

    ws.onopen = function () {
      console.log("WebSocket connection established");
    };
    ws.on("message", (messageAsString) => {
      const message = JSON.parse(messageAsString);
      const metadata = clients.get(ws);

      message.sender = metadata.id;
      message.color = metadata.color;

      [...clients.keys()].forEach((client) => {
        client.send(JSON.stringify(message));
      });
    });

    ws.on("close", () => {
      clients.delete(ws);
    });

    ws.onerror = function (error) {
      console.error("WebSocket error:", error);
      // You can add more detailed error logging here
    };
  });
}

export { setupWebSocket };
