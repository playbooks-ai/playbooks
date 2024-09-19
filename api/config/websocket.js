import { v4 as uuidv4 } from "uuid";

const clients = new Map();

function setupWebSocket(wss) {
  wss.on("connection", (ws) => {
    const id = uuidv4();
    const color = Math.floor(Math.random() * 360);
    const metadata = { id, color };

    clients.set(ws, metadata);

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
  });
}

export { setupWebSocket };
