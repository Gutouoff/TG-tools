import { test as base, expect, type Page } from '@playwright/test';

export const FIXED_TIME = new Date('2026-10-28T10:00:00+08:00').getTime();

export const accounts = [
  {
    name: 'acc_alpha', path: 'D:\\TG\\acc_alpha', state: 'session',
    phone: '13800000001', username: 'alpha_user', uid: '100000001',
    display: 'Alpha', avatar: '', country: 'CN',
  },
  {
    name: 'acc_beta', path: 'D:\\TG\\acc_beta', state: 'tdata',
    phone: '13800000002', username: 'beta_user', uid: '100000002',
    display: 'Beta', avatar: '', country: 'US', poll_alive: false, poll_msg: '登录态失效', poll_time: '10:00',
  },
  {
    name: 'acc_gamma', path: 'D:\\TG\\acc_gamma', state: 'session',
    phone: '13800000003', username: 'gamma_user', uid: '100000003',
    display: 'Gamma', avatar: '', country: 'JP', poll_alive: null, poll_msg: '状态未知',
  },
];

export const settings = {
  pack_naming: '{name}_账号包',
  pack_password: '',
  theme_seed: '#356AE6',
  theme_bg: '#F9FAFC',
  theme_dark: '#EDF0F5',
  theme_topbar: '#FFFFFF',
  theme_mode: 'light',
  card_order: '基本信息,聊天,安全,删除,其他设置',
  proxy_mode: 'none',
  proxy_scheme: 'socks5',
  proxy_host: '',
  proxy_port: '',
  log_level: 'info',
  cur_group: 'all',
  join_links: [
    { name: '示例群', link: 'https://t.me/example', type: 'group' },
    { name: '示例频道', link: 'https://t.me/example_channel', type: 'channel' },
  ],
};

export const logs = [
  { ts: '2026-10-28 10:00:00', level: 'info', msg: '程序版本： v1.2.3' },
  { ts: '2026-10-28 10:00:01', level: 'info', msg: '已加载 3 个账号' },
  { ts: '2026-10-28 10:00:02', level: 'warn', msg: '示例告警：网络较慢' },
];

export const dialogs = [
  { id: 1, name: '示例会话', type: 'user', last_date: '10:00', last_text: '你好', unread: 2 },
  { id: 2, name: '示例群组', type: 'group', last_date: '09:58', last_text: '群消息', unread: 0 },
];

async function json(route: any, body: unknown) {
  await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
}

/** 静态托管页面时拦截所有 /api/*，返回固定数据，保证截图与断言可复现。 */
export async function installMocks(page: Page) {
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const p = url.pathname;
    if (p === '/api/accounts') return json(route, accounts);
    if (p === '/api/settings') return json(route, settings);
    if (p === '/api/ping') return json(route, { status: 'ok', app: 'TG工具箱', version: '1.2.3' });
    if (p === '/api/logs') return json(route, { ok: true, items: logs, file: 'logs/tg-tool-20261028.log' });
    if (p === '/api/online') return json(route, { ok: true, online: [{ name: 'acc_alpha' }] });
    if (p === '/api/groups') return json(route, { 测试组: ['acc_beta'] });
    if (p === '/api/recv') return json(route, { on: false, rules: { exclude_channels: false, exclude_groups: false, exclude_bots: false } });
    if (p === '/api/rename-pending') return json(route, { ok: true, items: [{ old: 'acc_gamma', new: 'gamma_renamed' }] });
    if (p === '/api/whitelist') return json(route, { users: [5434838648], groups: [2284618069] });
    if (p === '/api/dialogs') return json(route, { ok: true, dialogs });
    if (p === '/api/chat/history') return json(route, { ok: true, msgs: [] });
    if (p === '/api/passkeys') return json(route, { ok: true, passkeys: [] });
    if (p === '/api/devices') return json(route, { ok: true, devices: [] });
    if (p === '/api/2fa') return json(route, { ok: true, has_2fa: false });
    if (p === '/api/profile') return json(route, {
      ok: true,
      profile: { first: '', last: '', about: '', username: '', phone: '', photo: '' },
    });
    return json(route, { ok: true });
  });
}

/** 固定时间、禁用动画、屏蔽真实 WebSocket，让页面渲染完全确定。 */
export async function installDeterminism(page: Page) {
  await page.addInitScript((fixed) => {
    const RealDate = Date;
    // @ts-expect-error 测试注入
    window.Date = class extends RealDate {
      constructor(...args: any[]) {
        // @ts-expect-error 透传参数
        super(...(args.length ? args : [fixed]));
      }
      static now() { return fixed; }
    };
    class FakeWebSocket {
      url: string;
      readyState = 3;
      onopen: any = null;
      onmessage: any = null;
      onclose: any = null;
      onerror: any = null;
      constructor(url: string) { this.url = url; }
      send() {}
      close() {}
      addEventListener() {}
      removeEventListener() {}
    }
    // @ts-expect-error 测试替身
    window.WebSocket = FakeWebSocket;
  }, FIXED_TIME);

  await page.addInitScript(() => {
    document.addEventListener('DOMContentLoaded', () => {
      const style = document.createElement('style');
      style.textContent = `
        *, *::before, *::after {
          animation: none !important;
          transition: none !important;
          caret-color: transparent !important;
        }
        html { scrollbar-width: none; }
        ::-webkit-scrollbar { width: 0 !important; height: 0 !important; }
      `;
      document.head.appendChild(style);
    });
  });
}

export const test = base.extend<{ app: Page; appErrors: string[] }>({
  appErrors: async ({}, use) => {
    await use([]);
  },
  app: async ({ page, appErrors }, use) => {
    page.on('pageerror', (err) => appErrors.push(`pageerror: ${err.message}`));
    page.on('console', (msg) => {
      if (msg.type() !== 'error') return;
      const text = msg.text();
      if (text.includes('favicon')) return;
      appErrors.push(`console: ${text}`);
    });
    await installDeterminism(page);
    await installMocks(page);
    await page.goto('/?token=e2e');
    await page.waitForFunction(() => document.fonts.status === 'loaded');
    await use(page);
  },
});

export { expect };
