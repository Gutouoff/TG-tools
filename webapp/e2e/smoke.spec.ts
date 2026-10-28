import { test, expect } from './fixtures';

test('主界面：顶栏与账号列表', async ({ app }) => {
  await expect(app.locator('.topbar .title')).toHaveText('TG小号工具箱');
  await expect(app.locator('.list .item')).toHaveCount(3);
  await expect(app.locator('.list .item').nth(0)).toContainText('Alpha');
  await expect(app.locator('.list .item').nth(1)).toContainText('失效');
  await expect(app.locator('.list .item').nth(2)).toContainText('?');
  await expect(app.locator('.list .item').nth(2)).toContainText('待重命名');
  await expect(app.locator('.list .item').nth(0).locator('.online-dot')).toHaveCount(1);
});

test('设置弹窗：打开、切分区、关闭', async ({ app }) => {
  await app.locator('.topbar').getByText('设置', { exact: true }).click();
  await expect(app.locator('.settings-modal')).toBeVisible();
  await expect(app.locator('.set-heading h1')).toHaveText('通用');

  await app.locator('.set-nav-item', { hasText: '外观' }).click();
  await expect(app.locator('.swatch-grid')).toBeVisible();
  await expect(app.locator('.set-heading h1')).toHaveText('外观');

  await app.locator('.set-nav-item', { hasText: '白名单' }).click();
  await expect(app.locator('.set-content-body')).toContainText('用户白名单');

  await app.locator('.set-close').click();
  await expect(app.locator('.settings-modal')).toHaveCount(0);
});

test('右键菜单：打开与移出', async ({ app }) => {
  await app.locator('.list .item').first().click({ button: 'right' });
  await expect(app.locator('.ctx')).toBeVisible();
  await expect(app.locator('.ctx')).toContainText('移动分组');
  await expect(app.locator('.ctx')).toContainText('断开连接（保持其他在线）');
  await app.mouse.click(120, 600);
  await expect(app.locator('.ctx')).toHaveCount(0);
});

test('删除账号弹窗：勾选前禁用、勾选后可用', async ({ app }) => {
  await app.locator('.list .item').first().click();
  await app.locator('details.card[data-card="其他设置"] summary').click();
  await app.locator('details.card[data-card="其他设置"] md-outlined-button', { hasText: '删除账号' }).click();

  const modal = app.locator('.del-modal');
  await expect(modal).toBeVisible();
  const confirm = modal.locator('md-filled-button');
  await expect(confirm).toHaveAttribute('disabled', '');
  await modal.locator('.del-check input').check();
  await expect(confirm).not.toHaveAttribute('disabled', '');

  await modal.locator('md-outlined-button', { hasText: '取消' }).click();
  await expect(modal).toHaveCount(0);
});

test('新建账号弹窗：三种方式切换', async ({ app }) => {
  await app.locator('.topbar').getByText('新建账号', { exact: true }).click();
  const modal = app.locator('.addacc-modal');
  await expect(modal).toBeVisible();
  await expect(modal.locator('.addacc-drop')).toBeVisible();

  await modal.locator('.mode-item', { hasText: '手机号登录' }).click();
  await expect(modal.locator('.phonelogin-box')).toContainText('手机号码');

  await modal.locator('.mode-item', { hasText: '扫码登录' }).click();
  await expect(modal.locator('.qrlogin-box')).toBeVisible();

  await modal.locator('.set-close').click();
  await expect(modal).toHaveCount(0);
});

test('聊天：消息列表与发起聊天识别提示', async ({ app }) => {
  await app.locator('.list .item').first().click();
  await app.locator('.chat-entry', { hasText: '消息列表' }).click();
  await expect(app.locator('.dlg-list')).toBeVisible();
  await app.locator('.refresh-btn').click();
  await expect(app.locator('.dlg-list')).toContainText('示例会话');

  const input = app.locator('.start-chat-row input');
  await input.fill('@alpha_user');
  await expect(app.locator('.start-chat-hint')).toContainText('已识别');
  await expect(app.locator('.start-chat-hint')).toContainText('用户名');
});
