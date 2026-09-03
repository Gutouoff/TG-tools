<script lang="ts">
  import { onMount, flushSync } from 'svelte';
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
    getGroups,
    createGroup,
    moveAccount,
    convertTdata,
    importArchive,
    packAccount,
    fetchAvatars,
    getSettings,
    saveSettings,
    getMe,
    TOKEN,
    type Account,
    type LogEvent,
  } from './api';

  const AVATAR_COLORS = ['#E17076', '#7BC862', '#65AADD', '#A695E7', '#EE7AAE', '#6EC9CB', '#FAA774', '#FFA6C9'];

  let accounts = $state<Account[]>([]);
  let filtered = $state<Account[]>([]);
  let filterVersion = $state(0);
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

  let avatarFailed = $state<Set<string>>(new Set());
  function onAvatarError(name: string) {
    const next = new Set(avatarFailed);
    next.add(name);
    avatarFailed = next;
  }
  function avatarUrl(a: Account): string {
    return `/api/avatar-image?name=${encodeURIComponent(a.name)}&token=${encodeURIComponent(TOKEN)}`;
  }

  function applyFilter() {
    const q = search.trim().toLowerCase();
    const base = groupFiltered();
    const result = q
      ? base.filter((a) =>
          `${a.name} ${a.display} ${a.username} ${a.phone} ${a.uid}`.toLowerCase().includes(q),
        )
      : [...base];
    filtered.splice(0, filtered.length, ...result);
    filterVersion++;
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
    const acc = await getAccounts();
    flushSync(() => {
      accounts = acc;
      applyFilter();
    });
  }

  async function onConnect(a: Account) {
    current = a;
    addLog(`正在连接 ${a.name} …`);
    const r = await connectAccount(a.path);
    if (r.ok && r.info) {
      const uname = r.info.username || '';
      if (uname) {
        a.username = uname;
        applyFilter();
      }
      markOnline(a.name, true);
      addLog(`已连接 ${a.name}${uname ? ` (@${uname})` : ''}`);
    } else {
      addLog(`连接失败: ${r.msg || '未知错误'}`);
    }
  }

  async function doDisconnect() {
    await disconnect();
    connected = false;
    if (current) markOnline(current.name, false);
    addLog('已断开连接');
  }
  async function doReconnect() {
    if (!current) {
      addLog('请先选择账号');
      return;
    }
    await onConnect(current);
  }
  async function doPack() {
    if (!current) {
      addLog('请先选择账号');
      return;
    }
    const r = await packAccount(current.path, current.name);
    addLog(r.ok ? `打包完成: ${r.msg}` : `打包失败: ${r.msg}`);
  }

  // 在线账号集合(头像右下角橘点)
  let onlineNames = $state<Set<string>>(new Set());
  function markOnline(name: string, on: boolean) {
    const next = new Set(onlineNames);
    if (on) next.add(name);
    else next.delete(name);
    onlineNames = next;
  }

  async function doFetchAvatars() {
    addLog('开始一键获取头像(后台,每号间隔1s)…');
    const r = await fetchAvatars();
    addLog(r.ok ? '头像获取任务已启动' : `失败: ${r.msg}`);
  }

  // 速度分段(五档: 极快/快速/默认/慢速/极慢)
  let speedVal = $state(3);
  const SPEED_SEG: Array<[string, number]> = [
    ['极快', 1],
    ['快速', 2],
    ['默认', 3],
    ['慢速', 4],
    ['极慢', 5],
  ];
  function onSpeed(v: number) {
    speedVal = v;
    setSpeed(v);
  }

  // 设置
  const THEME_COLORS = ['#9BCFDC', '#66BB6A', '#9C27B0', '#FF9800'];
  let settings = $state<Record<string, string | boolean>>({});
  let settingsOpen = $state(false);
  async function loadSettings() {
    settings = {
      pack_naming: '{name}_账号包', pack_password: '', theme_seed: '#9BCFDC',
      proxy_mode: 'none', proxy_scheme: 'socks5', proxy_host: '', proxy_port: '',
    };
    settingsOpen = true;
    try {
      settings = await getSettings();
    } catch (e) {
      // 保持默认值
    }
  }
  async function doSaveSettings() {
    await saveSettings(settings);
    settingsOpen = false;
    addLog('设置已保存');
    applyTheme();
  }
  function applyTheme() {
    const seed = (settings.theme_seed as string) || '#9BCFDC';
    document.documentElement.style.setProperty('--md-sys-color-primary', seed);
    document.documentElement.style.setProperty('--md-sys-color-primary-container', seed);
  }

  async function showWhitelist() {
    const wl = await getWhitelist();
    addLog(`白名单用户: ${wl.users.join(', ') || '无'}`);
    addLog(`白名单群/频道: ${wl.groups.join(', ') || '无'}`);
  }

  // 右栏视图
  let rightView = $state<'log' | 'passkey' | '2fa' | 'email' | 'devices' | 'profile' | 'whitelist' | 'settings'>('log');
  function setView(v: typeof rightView) {
    flushSync(() => {
      rightView = v;
    });
  }
  let passkeys = $state<any[]>([]);
  let devices = $state<any[]>([]);
  let has2fa = $state(false);
  let emailInput = $state('');
  let codeInput = $state('');
  let new2fa = $state('');
  let cur2fa = $state('');

  async function loadPasskeys() {
    setView('passkey');
    const r = await getPasskeys();
    passkeys = r.ok ? r.passkeys : [];
  }
  async function loadDevices() {
    setView('devices');
    const r = await getDevices();
    devices = r.ok ? r.devices : [];
  }
  async function load2FA() {
    setView('2fa');
    const r = await get2FA();
    has2fa = r.has_2fa ?? false;
  }
  function showEmail() {
    setView('email');
  }
  async function doDeletePasskey(id: string) {
    await deletePasskey(id);
    addLog('通行密钥已删除');
    await loadPasskeys();
  }
  let pkQrImg = $state('');
  async function doInitPasskey() {
    const r = await initPasskey();
    if (r.ok && r.img) {
      pkQrImg = `data:image/png;base64,${r.img}`;
      addLog('二维码已生成，请用手机扫码绑定通行密钥');
    } else {
      pkQrImg = '';
      addLog(`生成失败: ${r.msg || r}`);
    }
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
    setView('profile');
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
    setView('whitelist');
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

  // 账号分组
  let groups = $state<Record<string, string[]>>({});
  let curGroup = $state('all');

  async function loadGroups() {
    groups = await getGroups();
  }
  function groupFiltered(): Account[] {
    const grouped = new Set<string>();
    for (const names of Object.values(groups)) for (const n of names) grouped.add(n);
    if (curGroup === 'ungrouped') return accounts.filter((a) => !grouped.has(a.name));
    if (curGroup !== 'all') return accounts.filter((a) => (groups[curGroup] || []).includes(a.name));
    return accounts;
  }
  function selectGroup(g: string) {
    curGroup = g;
    applyFilter();
  }
  async function doCreateGroup() {
    const name = prompt('输入分组名称：');
    if (!name) return;
    const r = await createGroup(name.trim());
    if (r.ok) groups = r.groups;
    else addLog(`新建失败: ${r.msg}`);
  }
  async function doMoveAccount(name: string, group: string) {
    const r = await moveAccount(name, group);
    if (r.ok) {
      groups = r.groups;
      applyFilter();
    }
  }
  let ctxMenu = $state<{ x: number; y: number; name: string } | null>(null);
  function onAccountContext(e: MouseEvent, a: Account) {
    e.preventDefault();
    ctxMenu = { x: e.clientX, y: e.clientY, name: a.name };
  }
  function closeCtx() {
    ctxMenu = null;
  }

  // 三栏宽度拖动
  let leftW = $state(280);
  let midW = $state(340);
  let dragTarget = $state<'left' | 'mid' | null>(null);
  function startDrag(e: MouseEvent, t: 'left' | 'mid') {
    dragTarget = t;
    e.preventDefault();
  }
  function onWinMouseMove(e: MouseEvent) {
    if (!dragTarget) return;
    if (dragTarget === 'left') {
      leftW = Math.max(200, Math.min(500, e.clientX));
    } else {
      midW = Math.max(200, Math.min(700, e.clientX - leftW));
    }
  }
  function onWinMouseUp() {
    dragTarget = null;
  }

  // tdata 转换
  async function doConvertTdata(a: Account) {
    addLog(`正在转换 ${a.name} …`);
    const r = await convertTdata(a.path);
    addLog(r.ok ? `${a.name} 转换完成` : `${a.name} 转换失败: ${r.msg}`);
    await loadAccounts();
  }

  // 拖放导入
  function onDragOver(e: DragEvent) {
    e.preventDefault();
  }
  async function onDrop(e: DragEvent) {
    e.preventDefault();
    const files = e.dataTransfer?.files;
    if (!files?.length) return;
    for (const f of Array.from(files)) {
      if (!f.name.toLowerCase().endsWith('.zip')) continue;
      addLog(`正在导入 ${f.name} …`);
      const buf = await f.arrayBuffer();
      let bin = '';
      const bytes = new Uint8Array(buf);
      for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
      const r = await importArchive(btoa(bin), f.name.replace(/\.zip$/i, ''));
      addLog(r.ok ? `导入完成: ${r.msg}` : `导入失败: ${r.msg}`);
    }
    await loadAccounts();
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

  onMount(() => {
    loadGroups();
    loadAccounts();
  });
</script>

<header class="topbar">
  <span class="title">TG小号工具箱</span>
  <span class="conn" class:on={connected}>{connected ? '● 已连接' : '● 未连接'}</span>
  <button class="topbtn" onclick={doReconnect}>重新连接</button>
  <button class="topbtn" onclick={doDisconnect}>断开连接</button>
  <button class="topbtn" onclick={doPack}>打包</button>
  <button class="topbtn" onclick={loadSettings}>设置</button>
</header>

<svelte:window onmousemove={onWinMouseMove} onmouseup={onWinMouseUp} />
<div class="layout">
  <aside class="left" style="width:{leftW}px" ondragover={onDragOver} ondrop={onDrop} onclick={closeCtx}>
    <div class="groups">
      {#each ['all', 'ungrouped', ...Object.keys(groups)] as g}
        <button class="grp" class:on={curGroup === g} onclick={() => selectGroup(g)}>
          {g === 'all' ? '全部' : g === 'ungrouped' ? '未分组' : g}
        </button>
      {/each}
      <button class="grp add" onclick={doCreateGroup}>＋</button>
    </div>
    <input class="search" placeholder="搜索账号…" bind:value={search} oninput={onSearch} />
    <ul class="list">
      {#key filterVersion}
      {#each filtered as a}
        <li
          class="item"
          class:cur={current?.name === a.name}
          ondblclick={() => onConnect(a)}
          onclick={() => (current = a)}
          oncontextmenu={(e) => onAccountContext(e, a)}
        >
          <div class="avatar-wrap">
            {#if a.avatar && !avatarFailed.has(a.name)}
              <img class="avatar" src={avatarUrl(a)} alt="" onerror={() => onAvatarError(a.name)} />
            {:else}
              <span class="avatar" style="background:{avatarColor(a.name)}">{a.display?.[0] || a.username?.[0] || a.name[0] || '-'}</span>
            {/if}
            {#if onlineNames.has(a.name)}
              <span class="online-dot"></span>
            {/if}
          </div>
          <span class="meta">
            <span class="nm">{a.display || a.name}{a.username ? ` (@${a.username})` : ''}</span>
            <span class="sub">{a.country ? `${a.country} · ` : ''}{a.phone ? `+${a.phone}` : a.state}</span>
          </span>
          {#if a.state === 'tdata'}
            <button class="conv" onclick={(e) => { e.stopPropagation(); doConvertTdata(a); }}>转换</button>
          {/if}
        </li>
      {/each}
      {/key}
    </ul>
  </aside>

  {#if ctxMenu}
    <div class="ctx" style="left:{ctxMenu.x}px;top:{ctxMenu.y}px" onclick={(e) => e.stopPropagation()}>
      <div class="ctx-title">移动分组（可多选）</div>
      {#each Object.keys(groups) as g}
        <label class="ctx-check">
          <input
            type="checkbox"
            checked={(groups[g] || []).includes(ctxMenu.name)}
            onchange={() => doMoveAccount(ctxMenu.name, g)}
          />
          <span>{g}</span>
        </label>
      {/each}
      <button onclick={() => { doMoveAccount(ctxMenu.name, 'ungrouped'); closeCtx(); }}>移出所有分组</button>
    </div>
  {/if}

  <div class="splitter" onmousedown={(e) => startDrag(e, 'left')}></div>

  <section class="mid" style="width:{midW}px">
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
        <div class="speed-seg">
          {#each SPEED_SEG as [label, v]}
            <button class="seg" class:on={speedVal === v} onclick={() => onSpeed(v)}>{label}</button>
          {/each}
        </div>
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
        <md-outlined-button onclick={doFetchAvatars}>一键获取头像</md-outlined-button>
      </div>
    </details>
  </section>

  <div class="splitter" onmousedown={(e) => startDrag(e, 'mid')}></div>

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
        <button class="back" onclick={() => setView('log')}>← 返回</button>
      </div>
      <md-filled-button onclick={doInitPasskey}>＋ 添加通行密钥</md-filled-button>
      {#if pkQrImg}
        <div class="qr-box">
          <img class="qr-img" src={pkQrImg} alt="通行密钥二维码" />
        </div>
      {/if}
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
        <button class="back" onclick={() => setView('log')}>← 返回</button>
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
        <button class="back" onclick={() => setView('log')}>← 返回</button>
      </div>
      <input placeholder="邮箱地址" bind:value={emailInput} />
      <md-outlined-button onclick={doSendEmail}>发送验证码</md-outlined-button>
      <input placeholder="验证码" bind:value={codeInput} />
      <md-filled-button onclick={doVerifyEmail}>验证绑定</md-filled-button>
    {:else if rightView === 'devices'}
      <div class="sec-head">
        <h3>登录设备</h3>
        <button class="back" onclick={() => setView('log')}>← 返回</button>
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
        <button class="back" onclick={() => setView('log')}>← 返回</button>
      </div>
      <div class="form">
        <label>名字</label>
        <input bind:value={editFirstName} />
        <label>姓氏</label>
        <input bind:value={editLastName} />
        <label>用户名（不带 @）</label>
        <input bind:value={editUsername} />
        <label>简介</label>
        <textarea
          bind:value={editAbout}
          rows="1"
          oninput={(e) => {
            const t = e.currentTarget;
            t.style.height = 'auto';
            t.style.height = t.scrollHeight + 'px';
          }}
        ></textarea>
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
        <button class="back" onclick={() => setView('log')}>← 返回</button>
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

{#if settingsOpen}
  <div class="modal-mask" onclick={() => (settingsOpen = false)}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <div class="modal-head">
        <h3>设置</h3>
        <button class="back" onclick={() => (settingsOpen = false)}>✕</button>
      </div>
      <div class="form">
        <label>打包文件命名格式（name=账号名 date=日期）</label>
        <input bind:value={settings.pack_naming} />
        <label>默认压缩密码（暂未启用加密）</label>
        <input bind:value={settings.pack_password} />

        <label>代理模式</label>
        <select bind:value={settings.proxy_mode}>
          <option value="none">不使用代理</option>
          <option value="system">使用系统代理</option>
          <option value="manual">手动设置</option>
        </select>
        {#if settings.proxy_mode === 'manual'}
          <label>代理类型</label>
          <select bind:value={settings.proxy_scheme}>
            <option value="socks5">SOCKS5</option>
            <option value="socks4">SOCKS4</option>
            <option value="http">HTTP</option>
          </select>
          <label>IP 地址</label>
          <input bind:value={settings.proxy_host} placeholder="127.0.0.1" />
          <label>端口</label>
          <input bind:value={settings.proxy_port} placeholder="7890" />
        {/if}

        <label>色调</label>
        <div class="swatches">
          {#each THEME_COLORS as c}
            <button
              class="swatch"
              class:on={settings.theme_seed === c}
              style="background:{c}"
              onclick={() => { settings.theme_seed = c; applyTheme(); }}
            ></button>
          {/each}
          <input type="color" bind:value={settings.theme_seed} onchange={() => applyTheme()} />
        </div>

        <md-filled-button onclick={doSaveSettings}>保存设置</md-filled-button>
      </div>
    </div>
  </div>
{/if}

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
    display: flex;
    gap: 6px;
    padding: 12px;
    height: calc(100% - 64px);
  }
  .splitter {
    width: 6px;
    cursor: col-resize;
    flex-shrink: 0;
    border-radius: 3px;
  }
  .splitter:hover,
  .splitter:active {
    background: var(--md-sys-color-primary-container);
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
    flex-shrink: 0;
  }
  .right {
    flex: 1;
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
  .groups {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 8px;
  }
  .grp {
    background: none;
    border: 1px solid var(--md-sys-color-outline);
    color: var(--md-sys-color-on-surface);
    border-radius: 999px;
    padding: 4px 10px;
    cursor: pointer;
    font-size: 12px;
  }
  .grp.on {
    background: var(--md-sys-color-primary);
    color: var(--md-sys-color-on-primary);
    border-color: var(--md-sys-color-primary);
  }
  .grp.add {
    font-weight: 600;
  }
  .conv {
    background: none;
    border: 1px solid var(--md-sys-color-primary);
    color: var(--md-sys-color-primary);
    border-radius: 999px;
    padding: 2px 8px;
    cursor: pointer;
    font-size: 11px;
    flex-shrink: 0;
  }
  .ctx {
    position: fixed;
    z-index: 999;
    background: var(--md-sys-color-surface-container-high);
    border: 1px solid var(--md-sys-color-outline);
    border-radius: var(--md-sys-shape-corner-medium);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
    padding: 4px;
    min-width: 140px;
    display: flex;
    flex-direction: column;
  }
  .ctx-title {
    font-size: 12px;
    color: var(--md-sys-color-on-surface-variant);
    padding: 4px 8px;
  }
  .ctx button {
    background: none;
    border: none;
    text-align: left;
    padding: 6px 8px;
    cursor: pointer;
    font-size: 13px;
    color: var(--md-sys-color-on-surface);
    border-radius: 6px;
  }
  .ctx button:hover {
    background: var(--md-sys-color-primary-container);
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
    width: 48px;
    height: 48px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    color: #fff;
    font-weight: 600;
    flex-shrink: 0;
    font-size: 18px;
  }
  img.avatar {
    object-fit: cover;
  }
  .avatar-wrap {
    position: relative;
    flex-shrink: 0;
  }
  .online-dot {
    position: absolute;
    right: -1px;
    bottom: -1px;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #ff9100;
    border: 2px solid var(--md-sys-color-surface-container);
  }
  .avatar.big {
    width: 64px;
    height: 64px;
    font-size: 24px;
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
    flex: 1;
    min-width: 0;
  }
  .bi-name {
    font-size: 16px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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
  .topbtn {
    background: none;
    border: 1px solid #78909c;
    color: #eceff1;
    border-radius: 999px;
    padding: 5px 14px;
    cursor: pointer;
    font-size: 13px;
    margin-left: 8px;
  }
  .topbtn:hover {
    background: rgba(255, 255, 255, 0.1);
  }
  .conn {
    margin-right: 12px;
  }
  .edit-btn {
    margin-left: auto;
    flex-shrink: 0;
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
  .form select {
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
  .modal-mask {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    z-index: 999;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .modal {
    width: 440px;
    max-height: 86vh;
    background: var(--md-sys-color-surface-container);
    border-radius: var(--md-sys-shape-corner-large);
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
  }
  .modal-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }
  .modal-head h3 {
    margin: 0;
    font-size: 18px;
  }
  .swatches {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 4px 0 8px;
  }
  .swatch {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: 2px solid transparent;
    cursor: pointer;
    padding: 0;
  }
  .swatch.on {
    border-color: var(--md-sys-color-on-surface);
  }
  .swatches input[type='color'] {
    width: 36px;
    height: 32px;
    padding: 0;
    border: none;
    cursor: pointer;
    margin: 0;
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
  .speed-seg {
    display: flex;
    flex: 1;
    border: 1px solid var(--md-sys-color-outline);
    border-radius: 999px;
    overflow: hidden;
  }
  .seg {
    background: none;
    border: none;
    padding: 6px 0;
    cursor: pointer;
    font-size: 12px;
    color: var(--md-sys-color-on-surface);
    flex: 1;
  }
  .seg + .seg {
    border-left: 1px solid var(--md-sys-color-outline);
  }
  .seg.on {
    background: var(--md-sys-color-primary);
    color: var(--md-sys-color-on-primary);
  }
  .ctx-check {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    cursor: pointer;
    font-size: 13px;
    color: var(--md-sys-color-on-surface);
  }
  .ctx-check input {
    margin: 0;
  }
  .check-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--md-sys-color-on-surface-variant);
    margin-top: 6px;
  }
  .check-row input {
    width: auto;
    margin: 0;
  }
  .qr-box {
    display: flex;
    justify-content: center;
    padding: 12px 0;
  }
  .qr-img {
    width: 200px;
    height: 200px;
    border-radius: var(--md-sys-shape-corner-medium);
  }
  input[type='color'] {
    height: 40px;
    padding: 2px;
    cursor: pointer;
  }
  /* 美化滚动条 */
  .list::-webkit-scrollbar,
  .log::-webkit-scrollbar,
  .sec-list::-webkit-scrollbar,
  .form::-webkit-scrollbar {
    width: 8px;
  }
  .list::-webkit-scrollbar-thumb,
  .log::-webkit-scrollbar-thumb,
  .sec-list::-webkit-scrollbar-thumb,
  .form::-webkit-scrollbar-thumb {
    background: #b0bec5;
    border-radius: 4px;
  }
  .list::-webkit-scrollbar-track,
  .log::-webkit-scrollbar-track,
  .sec-list::-webkit-scrollbar-track,
  .form::-webkit-scrollbar-track {
    background: transparent;
  }
</style>
