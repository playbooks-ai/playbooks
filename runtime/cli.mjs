#!/usr/bin/env node

import { program } from "commander";
import dotenv from "dotenv";
import readline from "readline";
import PlaybookRuntime from "./main.js";
import { loadPlaybooks } from "./playbook.js";

dotenv.config();

program
  .option(
    "-p, --project <path>",
    "Path to the project folder containing playbooks and config.json"
  )
  .option(
    "-m, --model <name>",
    "LLM model to use",
    process.env.LLM_MODEL || "claude-3-5-sonnet-20240620"
  )
  .parse(process.argv);

const options = program.opts();

if (!options.project) {
  console.error(
    "Error: Project path is required. Use -p or --project to specify the path."
  );
  process.exit(1);
}

const [playbooks, config] = loadPlaybooks(options.project);
const runtime = new PlaybookRuntime(playbooks, config, options.model);

async function chat() {
  console.log('Chat session started. Type "exit" to quit.');

  // Generate and display welcome message
  process.stdout.write("AI: ");
  const welcomeResponse = await runtime.chat(
    "Start the conversation",
    (content) => {
      process.stdout.write(content);
    }
  );
  console.log(); // New line after the welcome message

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  const askQuestion = (query) => {
    return new Promise((resolve) => {
      rl.question(query, (answer) => {
        resolve(answer);
      });
    });
  };

  while (true) {
    const userInput = await askQuestion("Human: ");
    if (userInput.toLowerCase() === "exit") {
      break;
    }
    process.stdout.write("AI: ");
    await runtime.chat(userInput, (content) => {
      process.stdout.write(content);
    });
    console.log(); // New line after the AI's response
  }

  rl.close();
}

chat().catch((error) => {
  console.error("An error occurred:", error);
  process.exit(1);
});
