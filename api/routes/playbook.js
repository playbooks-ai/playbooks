import express from "express";
import PlaybookRuntime from "../../runtime/main.js";
const router = express.Router();

router.post("/run", async (req, res) => {
  const { playbook, config } = req.body;
  try {
    const runtime = new PlaybookRuntime("./examples/hello_world");
    const response = await runtime.chat(playbook);
    res.json({ message: "Playbook executed", response });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});
export default router;
