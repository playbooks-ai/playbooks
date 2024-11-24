import fs from "fs";
import { LLM } from "../llm.js";
import PlaybookRuntime from "../main.js";
import { createSystemPrompt, loadPlaybooks } from "../playbook.js";

jest.mock("../llm.js");
jest.mock("fs");
jest.mock("path");

describe("PlaybookRuntime", () => {
  let playbooks;
  let config;

  beforeEach(() => {
    playbooks = ["Playbook 1", "Playbook 2"];
    config = {
      agent_name: "TestAgent",
      description: "Test Description",
      personality: "Test Personality",
    };
  });

  test("constructor initializes correctly", () => {
    const runtime = new PlaybookRuntime(playbooks, config);
    expect(runtime.llm).toBeInstanceOf(LLM);
    expect(runtime.systemPrompt).toBeDefined();
    expect(runtime.session).toBeNull();
  });

  test("startConversation creates a new session", () => {
    const runtime = new PlaybookRuntime(playbooks, config);
    runtime.startConversation();
    expect(runtime.session).toBeDefined();
  });

  test("chat starts a new conversation if none exists", async () => {
    const runtime = new PlaybookRuntime(playbooks, config);
    const mockChat = jest.fn().mockResolvedValue("AI response");
    runtime.llm.chat = mockChat;

    await runtime.chat("Hello", jest.fn());

    expect(runtime.session).toBeDefined();
    expect(mockChat).toHaveBeenCalled();
  });
});

describe("loadPlaybooks", () => {
  beforeEach(() => {
    fs.readdirSync.mockReturnValue([
      "playbook1.md",
      "playbook2.md",
      "config.json",
    ]);
    fs.readFileSync.mockImplementation((filePath) => {
      if (filePath.endsWith(".md")) {
        return "Playbook content";
      } else if (filePath.endsWith("config.json")) {
        return JSON.stringify({ key: "value" });
      }
    });
    fs.existsSync.mockReturnValue(true);
  });

  test("loads playbooks and config correctly", () => {
    const [playbooks, config] = loadPlaybooks("/fake/path");
    expect(playbooks).toHaveLength(2);
    expect(playbooks[0]).toBe("Playbook content");
    expect(config).toEqual({ key: "value" });
  });
});

describe("createSystemPrompt", () => {
  test("creates system prompt with default values", () => {
    const playbooks = ["Playbook 1", "Playbook 2"];
    const config = {};
    const prompt = createSystemPrompt(playbooks, config);
    expect(prompt).toContain("Voltron");
    expect(prompt).toContain("A highly intelligent and professional AI agent");
    expect(prompt).toContain("friendly and funny");
  });

  test("creates system prompt with custom values", () => {
    const playbooks = ["Playbook 1", "Playbook 2"];
    const config = {
      agent_name: "CustomAgent",
      description: "Custom Description",
      personality: "serious and formal",
    };
    const prompt = createSystemPrompt(playbooks, config);
    expect(prompt).toContain("CustomAgent");
    expect(prompt).toContain("Custom Description");
    expect(prompt).toContain("serious and formal");
  });
});
