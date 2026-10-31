import { test, expect, type Page } from './fixtures';

async function settle(page: Page) {
  await page.mouse.move(0, 0);
  await page.waitForTimeout(60);
}

test('重命名弹窗：右键菜单打开、可取消', async ({ app }) => {
  await app.locator('.list .item').first().click({ button: 'right' });
  await app.locator('.ctx button', { hasText: '重命名文件夹' }).click();
  const modal = app.locator('.rename-modal').filter({ has: app.locator('.rename-input') });
  await expect(modal).toBeVisible();
  await expect(modal.locator('.rename-input')).toHaveAttribute('placeholder', '输入新的文件夹名称');
  await modal.locator('md-outlined-button', { hasText: '取消' }).click();
  await expect(modal).toHaveCount(0);
});

test('转换弹窗：tdata→session 与 session→tdata 都能打开', async ({ app }) => {
  await app.locator('.list .item').first().click();
  await app.locator('details.card[data-card="转换"] summary').click();

  await app.locator('details.card[data-card="转换"] md-outlined-button', { hasText: 'tdata 转 session+json' }).click();
  const t2s = app.locator('.rename-modal').filter({ hasText: '覆盖刷新会话' });
  await expect(t2s).toBeVisible();
  await expect(t2s).toContainText('在线账号仅刷新 json 元数据');
  await t2s.locator('md-outlined-button', { hasText: '取消' }).click();
  await expect(t2s).toHaveCount(0);

  await app.locator('details.card[data-card="转换"] md-outlined-button', { hasText: 'session+json 转 tdata' }).click();
  const conv = app.locator('.rename-modal').filter({ hasText: 'session 登录态转换为 Telegram Desktop' });
  await expect(conv).toBeVisible();
  await expect(conv.locator('.del-check')).toContainText('覆盖已有 tdata');
  await conv.locator('md-outlined-button', { hasText: '取消' }).click();
  await expect(conv).toHaveCount(0);
});

test('设置其他分区：代理/加群/关于均可渲染', async ({ app }) => {
  await app.locator('.topbar').getByText('设置', { exact: true }).click();
  await expect(app.locator('.settings-modal')).toBeVisible();

  await app.locator('.set-nav-item', { hasText: '代理' }).click();
  await expect(app.locator('.set-content-body')).toContainText('代理模式');

  await app.locator('.set-nav-item', { hasText: '加群频道' }).click();
  await expect(app.locator('.set-content-body')).toContainText('预选邮箱');

  await app.locator('.set-nav-item', { hasText: '关于' }).click();
  await expect(app.locator('.set-content-body')).toContainText('github.com/Gutouoff/TG-tools');

  await settle(app);
  await app.locator('.set-close').click();
  await expect(app.locator('.settings-modal')).toHaveCount(0);
});
