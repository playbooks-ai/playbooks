import cors from "cors";
import "dotenv/config";
import express from "express";
import http from "http";
import path, { dirname } from "path";
import { fileURLToPath } from "url";
import WebSocket from "ws";
import { setupWebSocket } from "./config/websocket.js";
import playbookRoutes from "./routes/playbook.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
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

// Add this after all your route definitions
app.use((req, res, next) => {
  console.log(`${req.method} ${req.url}`);
  next();
});

// List all routes
console.log("Registered routes:");
app._router.stack.forEach((middleware) => {
  if (middleware.route) {
    // Routes registered directly on the app
    console.log(
      `${Object.keys(middleware.route.methods)} ${middleware.route.path}`
    );
  } else if (middleware.name === "router") {
    // Router middleware
    middleware.handle.stack.forEach((handler) => {
      if (handler.route) {
        const path = handler.route.path;
        const methods = Object.keys(handler.route.methods);
        console.log(`${methods} /api/playbook${path}`);
      }
    });
  }
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
