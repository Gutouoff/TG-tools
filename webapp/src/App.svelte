<script lang="ts">
  import {
    getAccounts,
    connectAccount,
    disconnect,
    postTask,
    connectWS,
    setSpeed,
    updateTelegram,
    getWhitelist,
    type Account,
    type LogEvent,
  } from './api';

  const AVATAR_COLORS = ['#E17076', '#7BC862', '#65AADD', '#A695E7', '#EE7AAE', '#6EC9CB', '#FAA774', '#FFA6C9'];

  let accounts = $state<Account[]>([]);
  let filtered = $state<Account[]>([]);
  let search = $state('');
  let current = $state<Account | null>(null);
  let connected = $state(false);
  let logs = $state<string[]>([]);
  let progress = $state({ done: 0, total: 0, label: '' });

  function avatarColor(name: string): string {
    let h = 0;
    for (const c of name) h = (h * 31 + c.charCodeAt(0)) | 0;
    return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
  }

  function applyFilter() {
    const q = search.trim().toLowerCase();
    filtered = q
      ? accounts.filter((a) =>
          `${a.name} ${a.display} ${a.username} ${a.phone} ${a.uid}`.toLowerCase().includes(q),
        )
      : accounts;
  }

  let searchTimer: ReturnType<typeof setTimeout> | undefined;
  function onSearch() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(applyFilter, 300);
  }

  function addLog(line: string) {
    logs = [...logs, line].slice(-2000);
  }

  async function loadAccounts() {
    accounts = await getAccounts();
    applyFilter();
  }

  async function onConnect(a: Account) {
    current = a;
    addLog(`正在连接 ${a.name} …`);
    await connectAccount(a.path);
  }

  async function showWhitelist() {
    const wl = await getWhitelist();
    addLog(`白名单用户: ${wl.users.join(', ') || '无'}`);
    addLog(`白名单群/频道: ${wl.groups.join(', ') || '无'}`);
  }

  connectWS((e: LogEvent) => {
    if (e.type === 'log' && e.line) addLog(e.line);
    if (e.type === 'progress') {
      progress = { done: e.done ?? 0, total: e.total ?? 0, label: e.label ?? '' };
    }
    if (e.type === 'state') {
      if (e.status === 'connected') connected = true;
      if (e.status === 'connect_fail') connected = false;
      if (e.status === 'done') addLog('[完成]');
      if (e.status === 'error') addLog(`[错误] ${String(e.data ?? '')}`);
    }
  });

  loadAccounts();
</script>

<header class="topbar">
  <span class="title">TG小号工具箱</span>
  <span class="conn" class:on={connected}>{connected ? '● 已连接' : '● 未连接'}</span>
</header>

<div class="layout">
  <aside class="left">
    <input class="search" placeholder="搜索账号…" bind:value={search} oninput={onSearch} />
    <ul class="list">
      {#each filtered as a (a.name)}
        <li
          class="item"
          class:cur={current?.name === a.name}
          ondblclick={() => onConnect(a)}
          onclick={() => (current = a)}
        >
          <span class="avatar" style="background:{avatarColor(a.name)}">{a.display?.[0] || a.name[0] || '-'}</span>
          <span class="meta">
            <span class="nm">{a.display || a.name}</span>
            <span class="sub">@{a.username || a.phone || a.state}</span>
          </span>
        </li>
      {/each}
    </ul>
  </aside>

  <section class="mid">
    <details class="card" open>
      <summary>删除</summary>
      <div class="grid">
        <md-filled-button onclick={() => postTask('/api/tasks/delete-contacts')}>删联系人</md-filled-button>
        <md-outlined-button onclick={() => postTask('/api/tasks/delete-dialogs', { choice: 'users' })}>删对话</md-outlined-button>
        <md-outlined-button onclick={() => postTask('/api/tasks/delete-dialogs', { choice: 'bots' })}>删机器人</md-outlined-button>
        <md-outlined-button onclick={() => postTask('/api/tasks/delete-dialogs', { choice: 'groups' })}>删频道</md-outlined-button>
      </div>
      <div class="speed-row">
        <span class="speed-label">速度</span>
        {#each ['极快', '快速', '默认', '慢速', '极慢'] as s, i}
          <label class="speed-item">
            <input type="radio" name="speed" value={i + 1} checked={i === 2} onchange={() => setSpeed(i + 1)} />
            <span>{s}</span>
          </label>
        {/each}
      </div>
    </details>

    <details class="card" open>
      <summary>基本信息</summary>
      <div class="bi">
        <span class="avatar big" style="background:{avatarColor(current?.name || '-')}">
          {current?.display?.[0] || current?.name?.[0] || '-'}
        </span>
        <div class="bi-meta">
          <div class="bi-name">{current?.display || current?.name || '未选择账号'}</div>
          <div class="bi-sub">@{current?.username || current?.phone || '-'}</div>
        </div>
      </div>
    </details>

    <details class="card">
      <summary>安全</summary>
      <div class="grid">
        <md-outlined-button>两步验证</md-outlined-button>
        <md-outlined-button>通行密钥</md-outlined-button>
        <md-outlined-button>邮箱登录</md-outlined-button>
        <md-outlined-button>登录设备</md-outlined-button>
      </div>
    </details>

    <details class="card">
      <summary>其他设置</summary>
      <div class="grid">
        <md-outlined-button onclick={() => updateTelegram()}>更新本体</md-outlined-button>
        <md-outlined-button onclick={showWhitelist}>白名单管理</md-outlined-button>
      </div>
    </details>
  </section>

  <section class="right">
    <div class="prog">
      <span>{progress.label || '无任务'}</span>
      <span>{progress.total ? `${progress.done}/${progress.total}` : ''}</span>
    </div>
    <ul class="log">
      {#each logs as l}<li>{l}</li>{/each}
    </ul>
  </section>
</div>

<style>
  .topbar {
    display: flex;
    align-items: center;
    height: 64px;
    padding: 0 24px;
    background: #37474f;
    color: #eceff1;
  }
  .title {
    font-size: 20px;
    font-weight: 600;
  }
  .conn {
    margin-left: auto;
    font-size: 13px;
    color: #b0bec5;
  }
  .conn.on {
    color: #a5d6a7;
  }
  .layout {
    display: grid;
    grid-template-columns: 320px 1fr 1.4fr;
    gap: 8px;
    padding: 12px;
    height: calc(100% - 64px);
  }
  .left,
  .mid,
  .right {
    background: var(--md-sys-color-surface-container);
    border-radius: var(--md-sys-shape-corner-large);
    padding: 12px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .search {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--md-sys-color-outline);
    border-radius: 999px;
    background: var(--md-sys-color-surface);
    color: var(--md-sys-color-on-surface);
    font-size: 14px;
    outline: none;
    margin-bottom: 8px;
  }
  .list {
    list-style: none;
    margin: 0;
    padding: 0;
    overflow-y: auto;
    flex: 1;
  }
  .item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-radius: var(--md-sys-shape-corner-medium);
    cursor: pointer;
  }
  .item:hover {
    background: var(--md-sys-color-surface-container-high);
  }
  .item.cur {
    background: var(--md-sys-color-primary-container);
  }
  .avatar {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    color: #fff;
    font-weight: 600;
    flex-shrink: 0;
  }
  .avatar.big {
    width: 56px;
    height: 56px;
    font-size: 20px;
  }
  .meta {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .nm {
    font-size: 14px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .sub {
    font-size: 12px;
    color: var(--md-sys-color-on-surface-variant);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .card {
    background: var(--md-sys-color-surface);
    border-radius: var(--md-sys-shape-corner-large);
    margin-bottom: 8px;
    overflow: hidden;
  }
  .card summary {
    padding: 12px 16px;
    cursor: pointer;
    font-weight: 600;
    font-size: 15px;
    list-style: none;
    display: flex;
    align-items: center;
  }
  .card summary::before {
    content: '▸';
    margin-right: 8px;
    transition: transform 0.15s;
    font-size: 12px;
  }
  .card[open] summary::before {
    content: '▾';
  }
  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    padding: 0 16px 12px;
  }
  .grid md-filled-button,
  .grid md-outlined-button {
    width: 100%;
  }
  .speed-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 16px 12px;
    flex-wrap: wrap;
  }
  .speed-label {
    font-size: 13px;
    color: var(--md-sys-color-on-surface-variant);
  }
  .speed-item {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    cursor: pointer;
  }
  .bi {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0 16px 12px;
  }
  .bi-meta {
    display: flex;
    flex-direction: column;
  }
  .bi-name {
    font-size: 16px;
    font-weight: 600;
  }
  .bi-sub {
    font-size: 13px;
    color: var(--md-sys-color-on-surface-variant);
  }
  .prog {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--md-sys-color-outline);
  }
  .log {
    list-style: none;
    margin: 8px 0 0;
    padding: 0;
    overflow-y: auto;
    flex: 1;
    font-family: 'Consolas', monospace;
    font-size: 12px;
  }
  .log li {
    padding: 2px 0;
    white-space: pre-wrap;
    word-break: break-all;
  }
</style>
