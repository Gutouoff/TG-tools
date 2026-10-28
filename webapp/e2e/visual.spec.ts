import { test, expect, type Page } from './fixtures';

async function settle(page: Page) {
  await page.mouse.move(0, 0);
  await page.waitForTimeout(80);
}

test('视觉基线：主界面', async ({ app }) => {
  await settle(app);
  await expect(app).toHaveScreenshot('01-home.png');
});

test('视觉基线：设置-通用', async ({ app }) => {
  await app.locator('.topbar').getByText('设置', { exact: true }).click();
  await expect(app.locator('.settings-modal')).toBeVisible();
  await settle(app);
  await expect(app).toHaveScreenshot('02-settings-general.png');
});

test('视觉基线：设置-外观', async ({ app }) => {
  await app.locator('.topbar').getByText('设置', { exact: true }).click();
  await app.locator('.set-nav-item', { hasText: '外观' }).click();
  await expect(app.locator('.swatch-grid')).toBeVisible();
  await settle(app);
  await expect(app).toHaveScreenshot('03-settings-appearance.png');
});

test('视觉基线：右键菜单', async ({ app }) => {
  await app.locator('.list .item').first().click({ button: 'right' });
  await expect(app.locator('.ctx')).toBeVisible();
  await settle(app);
  await expect(app).toHaveScreenshot('04-context-menu.png');
});

test('视觉基线：删除账号弹窗', async ({ app }) => {
  await app.locator('.list .item').first().click();
  await app.locator('details.card[data-card="其他设置"] summary').click();
  await app.locator('details.card[data-card="其他设置"] md-outlined-button', { hasText: '删除账号' }).click();
  await expect(app.locator('.del-modal')).toBeVisible();
  await settle(app);
  await expect(app).toHaveScreenshot('05-delete-dialog.png');
});

test('视觉基线：会话列表', async ({ app }) => {
  await app.locator('.list .item').first().click();
  await app.locator('.chat-entry', { hasText: '消息列表' }).click();
  await expect(app.locator('.dlg-list')).toBeVisible();
  await app.locator('.refresh-btn').click();
  await expect(app.locator('.dlg-list')).toContainText('示例会话');
  await settle(app);
  await expect(app).toHaveScreenshot('06-chat-list.png');
});

test('视觉基线：加群频道视图', async ({ app }) => {
  await app.locator('.list .item').first().click();
  await app.locator('details.card[data-card="其他设置"] summary').click();
  await app.locator('details.card[data-card="其他设置"] md-outlined-button', { hasText: '加群频道' }).click();
  await expect(app.locator('.join-cat').first()).toBeVisible();
  await settle(app);
  await expect(app).toHaveScreenshot('07-join-view.png');
});

test('视觉基线：新建账号弹窗', async ({ app }) => {
  await app.locator('.topbar').getByText('新建账号', { exact: true }).click();
  await expect(app.locator('.addacc-modal')).toBeVisible();
  await settle(app);
  await expect(app).toHaveScreenshot('11-add-account.png');
});

test('视觉基线：资料编辑', async ({ app }) => {
  await app.locator('.list .item').first().click();
  await app.locator('.edit-btn').click();
  await expect(app.locator('.form')).toBeVisible();
  await settle(app);
  await expect(app).toHaveScreenshot('08-profile.png');
});
