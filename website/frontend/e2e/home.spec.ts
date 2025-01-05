import { test, expect } from '@playwright/test';

test('home page loads successfully', async ({ page }) => {
  // Navigate to the home page
  await page.goto('/');

  // Wait for the main content to be visible
  await expect(page.locator('main')).toBeVisible();

  // Verify key elements are present
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();

  // Check for any console errors
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(`Console error: ${msg.text()}`);
    }
  });

  // Assert no errors occurred during page load
  expect(errors).toHaveLength(0);
});
