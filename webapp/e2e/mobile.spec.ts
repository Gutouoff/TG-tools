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

test('手机端：选中账号后的当前页', async ({ app }) => {
  await app.locator('.mobile-account-row .mobile-account-main').first().click();
  await expect(app.locator('.mobile-current-card')).toContainText('Alpha');
  await expect(app.locator('.mobile-action-list')).toContainText('个人资料');
  await expect(app.locator('.mobile-quick-grid')).toContainText('删联系人');
});

test('手机端：动态页显示日志', async ({ app }) => {
  await app.locator('.mobile-nav button', { hasText: '动态' }).click();
  await expect(app.locator('.mobile-log-list')).toContainText('程序版本');
  await expect(app.locator('.mobile-log-list li').first()).toBeVisible();
});
