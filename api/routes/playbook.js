import express from "express";
import path from "path";
import { fileURLToPath } from "url";
import PlaybookRuntime from "../../runtime/main.js";

const router = express.Router();

// Get the directory name of the current module
const __dirname = path.dirname(fileURLToPath(import.meta.url));

router.post("/run", async (req, res) => {
  const { playbook, config, conversationHistory } = req.body;
  try {
    const runtime = new PlaybookRuntime([playbook], config);
    const result = await runtime.chat("Start the conversation", conversationHistory);
    res.json(result);
  } catch (error) {
    console.error("Error running playbook:", error);
    res.status(500).json({ error: "Internal server error" });
  }
});

export default router;
