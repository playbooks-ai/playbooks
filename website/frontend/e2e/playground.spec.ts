import { test, expect } from '@playwright/test';

test('playground functions correctly', async ({ page }) => {
  // Navigate to the home page
  await page.goto('/');

  // Wait for the editor to be visible
  await expect(page.locator('.monaco-editor')).toBeVisible();

  // Wait for the content to be loaded into the editor
  await page.waitForTimeout(1000); // Give editor time to update

  // Check if the example playbook content is loaded
  const editorContent = await page.locator('.monaco-editor').textContent();
  expect(editorContent).toBeTruthy();
  expect(editorContent).toContain('Hello');

  // Verify that the editor is interactive
  await expect(page.locator('.monaco-editor')).toBeEditable();

  // ==============================================

  // Click Run Playbook and wait for completion
  const runButton = page.getByTestId('run-playbook-button');
  await expect(runButton).toBeVisible();
  await expect(runButton).toBeEnabled();

  await runButton.click();

  // Wait for button to show loading state
  await expect(runButton).toHaveText('Running...');

  // Wait for button to return to normal state (indicating completion)
  await expect(runButton).toHaveText('Run Playbook', { timeout: 10000 });

  // ==============================================

  // Verify chat interface elements are present
  const chatContainer = page.getByTestId('chat-container');
  await expect(chatContainer).toBeVisible();

  // Check input field and send button
  const chatInput = page.getByTestId('chat-input');
  const sendButton = page.getByTestId('chat-send-button');
  await expect(chatInput).toBeVisible();
  await expect(chatInput).toBeEnabled();
  await expect(sendButton).toBeVisible();
  await expect(sendButton).toBeEnabled();

  // Wait for initial assistant message after playbook run
  await expect(page.getByTestId('chat-message-assistant')).toBeVisible({ timeout: 10000 });

  // ==============================================

  // Test sending a message with user's name and receiving agent response
  await chatInput.fill('My name is Amol. What is your name?');
  await sendButton.click();

  // Wait for user message to appear
  await expect(page.getByTestId('chat-message-user')).toBeVisible();

  // Wait for both assistant messages to be present
  const assistantMessages = page.getByTestId('chat-message-assistant');
  await expect(assistantMessages).toHaveCount(2, { timeout: 10000 });

  // Verify message contents are displayed properly
  const messages = await page.getByTestId('message-content').allTextContents();
  expect(messages.length).toBeGreaterThanOrEqual(3); // Initial assistant + user + response assistant
  expect(messages[0]).toBeTruthy();

  // ==============================================
  // To check conversation history, ask user's name and receive agent response
  await chatInput.fill('What is my name?');
  await sendButton.click();

  // Wait for user message to appear
  await expect(page.getByTestId('chat-message-user')).toHaveCount(2);

  // Wait for 3 assistant messages to be present
  const assistantMessages3 = page.getByTestId('chat-message-assistant');
  await expect(assistantMessages3).toHaveCount(3, { timeout: 10000 });

  // Last assistant message should have "name" in its content
  const lastAssistantMessage = await page.getByTestId('chat-message-assistant').last();
  const lastAssistantMessageContent = await lastAssistantMessage
    .getByTestId('message-content')
    .textContent();
  expect(lastAssistantMessageContent).toContain('Amol');

  // Verify message contents are displayed properly
  const messages4 = await page.getByTestId('message-content').allTextContents();
  expect(messages4.length).toBeGreaterThanOrEqual(5); // Initial assistant + user + response assistant
  expect(messages4[0]).toBeTruthy();

  // ==============================================

  // Check for any console errors
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(`Console error: ${msg.text()}`);
    }
  });

  // Assert no errors occurred during interaction
  expect(errors).toHaveLength(0);
});
