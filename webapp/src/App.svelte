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
    addWhitelistUser,
    addWhitelistGroup,
    removeWhitelistUser,
    removeWhitelistGroup,
    getPasskeys,
    deletePasskey,
    initPasskey,
    get2FA,
    set2FA,
    sendEmailCode,
    verifyEmailCode,
    getDevices,
    deleteDevice,
    getProfile,
    updateProfile,
    updateUsername,
    updateBirthday,
    uploadAvatar,
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

  // 右栏视图
  let rightView = $state<'log' | 'passkey' | '2fa' | 'email' | 'devices'>('log');
  let passkeys = $state<any[]>([]);
  let devices = $state<any[]>([]);
  let has2fa = $state(false);
  let emailInput = $state('');
  let codeInput = $state('');
  let new2fa = $state('');
  let cur2fa = $state('');

  async function loadPasskeys() {
    rightView = 'passkey';
    const r = await getPasskeys();
    passkeys = r.ok ? r.passkeys : [];
  }
  async function loadDevices() {
    rightView = 'devices';
    const r = await getDevices();
    devices = r.ok ? r.devices : [];
  }
  async function load2FA() {
    rightView = '2fa';
    const r = await get2FA();
    has2fa = r.has_2fa ?? false;
  }
  function showEmail() {
    rightView = 'email';
  }
  async function doDeletePasskey(id: string) {
    await deletePasskey(id);
    addLog('通行密钥已删除');
    await loadPasskeys();
  }
  async function doInitPasskey() {
    const r = await initPasskey();
    addLog(r.ok ? '二维码已生成' : `生成失败: ${r}`);
  }
  async function doDeleteDevice(hash: number) {
    await deleteDevice(hash);
    addLog('设备已注销');
    await loadDevices();
  }
  async function doSendEmail() {
    const r = await sendEmailCode(emailInput);
    addLog(r.ok ? '验证码已发送' : `发送失败: ${r.msg}`);
  }
  async function doVerifyEmail() {
    const r = await verifyEmailCode(codeInput);
    addLog(r.ok ? '邮箱绑定成功' : `验证失败: ${r.msg}`);
  }
  async function doSet2FA() {
    const r = await set2FA(cur2fa, new2fa);
    addLog(r.ok ? '2FA 设置成功' : `设置失败: ${r.msg}`);
  }

  // 资料编辑
  let editFirstName = $state('');
  let editLastName = $state('');
  let editUsername = $state('');
  let editAbout = $state('');
  let editDay = $state('');
  let editMonth = $state('');
  let editYear = $state('');

  async function loadProfile() {
    rightView = 'profile';
    editFirstName = current?.display || '';
    editUsername = current?.username || '';
    const r = await getProfile();
    if (r.ok && r.profile) {
      editAbout = r.profile.about || '';
      if (r.profile.birthday) {
        editDay = String(r.profile.birthday.day || '');
        editMonth = String(r.profile.birthday.month || '');
        editYear = String(r.profile.birthday.year || '');
      }
    }
  }
  async function doSaveProfile() {
    await updateUsername(editUsername);
    await updateProfile(editFirstName, editLastName, editAbout);
    if (editDay && editMonth) {
      await updateBirthday(Number(editDay), Number(editMonth), editYear ? Number(editYear) : null);
    }
    addLog('资料已提交更新');
  }
  async function doUploadAvatar(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    const buf = await file.arrayBuffer();
    let bin = '';
    const bytes = new Uint8Array(buf);
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    await uploadAvatar(btoa(bin));
    addLog('头像已上传');
  }

  // 白名单管理
  let wlUsers = $state<number[]>([]);
  let wlGroups = $state<number[]>([]);
  let wlUserInput = $state('');
  let wlGroupInput = $state('');

  async function loadWhitelist() {
    rightView = 'whitelist';
    const wl = await getWhitelist();
    wlUsers = wl.users;
    wlGroups = wl.groups;
  }
  async function doAddUser() {
    if (!wlUserInput) return;
    const r = await addWhitelistUser(Number(wlUserInput));
    wlUsers = r.users;
    wlUserInput = '';
  }
  async function doAddGroup() {
    if (!wlGroupInput) return;
    const r = await addWhitelistGroup(Number(wlGroupInput));
    wlGroups = r.groups;
    wlGroupInput = '';
  }
  async function doRemoveUser(id: number) {
    const r = await removeWhitelistUser(id);
    wlUsers = r.users;
  }
  async function doRemoveGroup(id: number) {
    const r = await removeWhitelistGroup(id);
    wlGroups = r.groups;
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
  {#if connected}
    <button class="disconnect" onclick={disconnect}>断开</button>
  {/if}
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
        <button class="edit-btn" onclick={loadProfile}>编辑</button>
      </div>
    </details>

    <details class="card">
      <summary>安全</summary>
      <div class="grid">
        <md-outlined-button onclick={load2FA}>两步验证</md-outlined-button>
        <md-outlined-button onclick={loadPasskeys}>通行密钥</md-outlined-button>
        <md-outlined-button onclick={showEmail}>邮箱登录</md-outlined-button>
        <md-outlined-button onclick={loadDevices}>登录设备</md-outlined-button>
      </div>
    </details>

    <details class="card">
      <summary>其他设置</summary>
      <div class="grid">
        <md-outlined-button onclick={() => updateTelegram()}>更新本体</md-outlined-button>
        <md-outlined-button onclick={loadWhitelist}>白名单管理</md-outlined-button>
      </div>
    </details>
  </section>

  <section class="right">
    {#if rightView === 'log'}
      <div class="prog">
        <span>{progress.label || '无任务'}</span>
        <span>{progress.total ? `${progress.done}/${progress.total}` : ''}</span>
      </div>
      <ul class="log">
        {#each logs as l}<li>{l}</li>{/each}
      </ul>
    {:else if rightView === 'passkey'}
      <div class="sec-head">
        <h3>通行密钥</h3>
        <button class="back" onclick={() => (rightView = 'log')}>← 返回</button>
      </div>
      <md-filled-button onclick={doInitPasskey}>＋ 添加通行密钥</md-filled-button>
      <ul class="sec-list">
        {#each passkeys as pk}
          <li class="sec-item">
            <span>{pk.name || '（未命名）'}</span>
            <button class="danger" onclick={() => doDeletePasskey(pk.id)}>删除</button>
          </li>
        {/each}
      </ul>
      {#if !passkeys.length}<p class="empty">暂无通行密钥</p>{/if}
    {:else if rightView === '2fa'}
      <div class="sec-head">
        <h3>两步验证</h3>
        <button class="back" onclick={() => (rightView = 'log')}>← 返回</button>
      </div>
      <p>当前状态：{has2fa ? '已开启' : '未开启'}</p>
      {#if has2fa}
        <input placeholder="当前密码" bind:value={cur2fa} />
      {/if}
      <input placeholder="新密码" bind:value={new2fa} />
      <md-filled-button onclick={doSet2FA}>设置/修改</md-filled-button>
    {:else if rightView === 'email'}
      <div class="sec-head">
        <h3>邮箱登录</h3>
        <button class="back" onclick={() => (rightView = 'log')}>← 返回</button>
      </div>
      <input placeholder="邮箱地址" bind:value={emailInput} />
      <md-outlined-button onclick={doSendEmail}>发送验证码</md-outlined-button>
      <input placeholder="验证码" bind:value={codeInput} />
      <md-filled-button onclick={doVerifyEmail}>验证绑定</md-filled-button>
    {:else if rightView === 'devices'}
      <div class="sec-head">
        <h3>登录设备</h3>
        <button class="back" onclick={() => (rightView = 'log')}>← 返回</button>
      </div>
      <ul class="sec-list">
        {#each devices as d}
          <li class="sec-item">
            <span>{d.device_model || '未知设备'}{d.current ? '（本设备）' : ''}</span>
            {#if !d.current}
              <button class="danger" onclick={() => doDeleteDevice(d.hash)}>删除</button>
            {/if}
          </li>
        {/each}
      </ul>
      {#if !devices.length}<p class="empty">暂无设备</p>{/if}
    {:else if rightView === 'profile'}
      <div class="sec-head">
        <h3>编辑资料</h3>
        <button class="back" onclick={() => (rightView = 'log')}>← 返回</button>
      </div>
      <div class="form">
        <label>名字</label>
        <input bind:value={editFirstName} />
        <label>姓氏</label>
        <input bind:value={editLastName} />
        <label>用户名（不带 @）</label>
        <input bind:value={editUsername} />
        <label>简介</label>
        <textarea bind:value={editAbout} rows="3"></textarea>
        <label>生日（月 / 日 / 年）</label>
        <div class="row3">
          <input placeholder="月" bind:value={editMonth} />
          <input placeholder="日" bind:value={editDay} />
          <input placeholder="年" bind:value={editYear} />
        </div>
        <label>头像</label>
        <input type="file" accept="image/*" onchange={doUploadAvatar} />
        <md-filled-button onclick={doSaveProfile}>保存</md-filled-button>
      </div>
    {:else if rightView === 'whitelist'}
      <div class="sec-head">
        <h3>白名单管理</h3>
        <button class="back" onclick={() => (rightView = 'log')}>← 返回</button>
      </div>
      <h4>用户白名单</h4>
      <div class="row2">
        <input placeholder="用户 ID" bind:value={wlUserInput} />
        <md-outlined-button onclick={doAddUser}>添加</md-outlined-button>
      </div>
      <ul class="sec-list">
        {#each wlUsers as u}
          <li class="sec-item"><span>{u}</span><button class="danger" onclick={() => doRemoveUser(u)}>移除</button></li>
        {/each}
      </ul>
      <h4>群/频道白名单</h4>
      <div class="row2">
        <input placeholder="群 ID" bind:value={wlGroupInput} />
        <md-outlined-button onclick={doAddGroup}>添加</md-outlined-button>
      </div>
      <ul class="sec-list">
        {#each wlGroups as g}
          <li class="sec-item"><span>{g}</span><button class="danger" onclick={() => doRemoveGroup(g)}>移除</button></li>
        {/each}
      </ul>
    {/if}
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
  .sec-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }
  .sec-head h3 {
    margin: 0;
    font-size: 17px;
  }
  .back {
    background: none;
    border: none;
    color: var(--md-sys-color-primary);
    cursor: pointer;
    font-size: 13px;
  }
  .sec-list {
    list-style: none;
    margin: 12px 0 0;
    padding: 0;
    overflow-y: auto;
    flex: 1;
  }
  .sec-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 8px;
    border-bottom: 1px solid var(--md-sys-color-outline);
    font-size: 14px;
  }
  .danger {
    background: none;
    border: 1px solid var(--md-sys-color-error);
    color: var(--md-sys-color-error);
    border-radius: 999px;
    padding: 4px 12px;
    cursor: pointer;
    font-size: 12px;
  }
  .empty {
    color: var(--md-sys-color-on-surface-variant);
    font-size: 13px;
    margin: 8px 0;
  }
  input {
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
  .right md-filled-button,
  .right md-outlined-button {
    margin-bottom: 8px;
  }
  .disconnect {
    background: none;
    border: 1px solid #b0bec5;
    color: #eceff1;
    border-radius: 999px;
    padding: 5px 14px;
    cursor: pointer;
    font-size: 13px;
  }
  .edit-btn {
    margin-left: auto;
    background: none;
    border: 1px solid var(--md-sys-color-primary);
    color: var(--md-sys-color-primary);
    border-radius: 999px;
    padding: 5px 14px;
    cursor: pointer;
    font-size: 12px;
  }
  .form {
    display: flex;
    flex-direction: column;
    gap: 4px;
    overflow-y: auto;
    flex: 1;
  }
  .form label {
    font-size: 13px;
    color: var(--md-sys-color-on-surface-variant);
    margin-top: 6px;
  }
  .form textarea {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--md-sys-color-outline);
    border-radius: var(--md-sys-shape-corner-medium);
    background: var(--md-sys-color-surface);
    color: var(--md-sys-color-on-surface);
    font-size: 14px;
    outline: none;
    font-family: inherit;
    resize: vertical;
  }
  .row2 {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 8px;
    align-items: center;
  }
  .row2 input {
    margin-bottom: 0;
  }
  .row3 {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 8px;
  }
</style>
