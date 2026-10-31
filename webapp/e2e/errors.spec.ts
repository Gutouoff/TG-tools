import { test, expect, type Page } from './fixtures';

test.setTimeout(120_000);

async function openCard(page: Page, name: string) {
  const card = page.locator(`details.card[data-card="${name}"]`);
  const open = await card.evaluate((el) => (el as HTMLDetailsElement).open);
  if (!open) await card.locator('summary').click();
}

async function walk(page: Page) {
  await page.locator('.list .item').first().click();
  await page.waitForTimeout(60);

  // 中栏六张卡展开，覆盖各卡内容渲染
  for (const name of ['基本信息', '聊天', '安全', '删除', '转换', '其他设置']) {
    await openCard(page, name);
  }

  // 设置六个分区
  await page.locator('.topbar').getByText('设置', { exact: true }).click();
  for (const name of ['通用', '外观', '代理', '加群频道', '白名单', '关于']) {
    await page.locator('.set-nav-item', { hasText: name }).click();
    await page.waitForTimeout(30);
  }
  await page.locator('.set-close').click();

  // 右栏视图：会话列表 -> 会话内 -> 返回
  await page.locator('.chat-entry', { hasText: '消息列表' }).click();
  await page.locator('.refresh-btn').click();
  await page.locator('.dlg-list .dlg').first().click();
  await page.waitForTimeout(60);
  await page.locator('.head-btns .back', { hasText: '会话列表' }).click();

  // 资料编辑
  await page.locator('.edit-btn').click();
  await page.waitForTimeout(60);
  await page.locator('.sec-head .back', { hasText: '日志' }).click();

  // 安全四视图
  await openCard(page, '安全');
  for (const name of ['两步验证', '登录设备', '通行密钥', '邮箱登录']) {
    await page.locator('details.card[data-card="安全"] md-outlined-button', { hasText: name }).click();
    await page.waitForTimeout(50);
  }

  // 加群频道视图
  await openCard(page, '其他设置');
  await page.locator('details.card[data-card="其他设置"] md-outlined-button', { hasText: '加群频道' }).click();
  await page.waitForTimeout(60);

  // 右键菜单 + 重命名弹窗
  await page.locator('.list .item').first().click({ button: 'right' });
  await page.locator('.ctx button', { hasText: '重命名文件夹' }).click();
  await page.locator('.rename-modal md-outlined-button', { hasText: '取消' }).click();

  // 删除账号弹窗
  await openCard(page, '其他设置');
  await page.locator('details.card[data-card="其他设置"] md-outlined-button', { hasText: '删除账号' }).click();
  await page.locator('.del-modal md-outlined-button', { hasText: '取消' }).click();
}

test('全界面走查：不应出现 JS 运行时错误', async ({ app, appErrors }) => {
  await walk(app);
  expect(appErrors, `页面报错：\n${appErrors.join('\n')}`).toEqual([]);
});
