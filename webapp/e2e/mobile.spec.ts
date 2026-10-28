import { test, expect, type Page } from './fixtures';

test.use({ viewport: { width: 390, height: 844 } });

async function settle(page: Page) {
  await page.mouse.move(0, 0);
  await page.waitForTimeout(80);
}

test('手机端：账号页', async ({ app }) => {
  await expect(app.locator('.mobile-app')).toBeVisible();
  await expect(app.locator('.mobile-account-row')).toHaveCount(3);
  await expect(app.locator('.mobile-account-row').nth(1)).toContainText('失效');
  await settle(app);
  await expect(app).toHaveScreenshot('09-mobile-accounts.png');
});

test('手机端：更多页', async ({ app }) => {
  await app.locator('.mobile-nav button', { hasText: '更多' }).click();
  await expect(app.locator('.mobile-version')).toBeVisible();
  await settle(app);
  await expect(app).toHaveScreenshot('10-mobile-more.png');
});
