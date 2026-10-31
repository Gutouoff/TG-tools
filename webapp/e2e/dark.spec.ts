import { test, expect, type Page } from './fixtures';

async function settle(page: Page) {
  await page.mouse.move(0, 0);
  await page.waitForTimeout(80);
}

test('暗色：主界面', async ({ darkApp }) => {
  await expect(darkApp.locator('html')).toHaveAttribute('data-theme', 'dark');
  await settle(darkApp);
  await expect(darkApp).toHaveScreenshot('12-dark-home.png');
});

test('暗色：设置-外观', async ({ darkApp }) => {
  await darkApp.locator('.topbar').getByText('设置', { exact: true }).click();
  await darkApp.locator('.set-nav-item', { hasText: '外观' }).click();
  await expect(darkApp.locator('.swatch-grid')).toBeVisible();
  await settle(darkApp);
  await expect(darkApp).toHaveScreenshot('13-dark-settings.png');
});
