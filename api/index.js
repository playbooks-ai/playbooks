require("dotenv").config();
const express = require("express");
const http = require("http");
const WebSocket = require("ws");
const path = require("path");
const { v4: uuidv4 } = require("uuid");
const playbookRoutes = require("./routes/playbook");
const { setupWebSocket } = require("./config/websocket");
const cors = require("cors");

const app = express();
// Enable CORS for all routes
app.use(
  cors({
    origin: "http://localhost:8080", // Allow requests from frontend
    methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allowedHeaders: ["Content-Type", "Authorization"],
  })
);

const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

app.use(express.static(path.join(__dirname, "../www")));
app.use(express.json());

const clients = new Map();

setupWebSocket(wss);

app.use("/api/playbook", playbookRoutes);

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
