<script lang="ts">
  const PANEL_TITLES: Record<string, string> = {
    log: '运行日志',
    chat: '消息与会话',
    profile: '个人资料',
    passkey: '通行密钥',
    '2fa': '两步验证',
    email: '邮箱登录',
    devices: '登录设备',
    join: '群组与频道',
  };

  let {
    mobilePanelOpen = $bindable(false),
    mobileTab = $bindable('accounts'),
    rightView,
    current,
    accounts,
    onlineNames,
    connected,
    connectingLabel,
    search = $bindable(''),
    filtered,
    groups,
    curGroup,
    avatarFailed,
    appVersion,
    progress,
    logs,
    themeMode,
    onSearch,
    onSelectGroup,
    onCreateGroup,
    onOpenAddAccount,
    onSelectAccount,
    avatarUrl,
    avatarColor,
    onAvatarError,
    onSwitch,
    onConnect,
    onLaunchClient,
    onOpenAccountFolder,
    onDisconnect,
    onReconnect,
    onLoadProfile,
    onOpenPanel,
    onDeleteContacts,
    onDeleteDialogs,
    onPack,
    onRefreshInfo,
    onReloadLogs,
    onLoadSettings,
    onToggleTheme,
  }: {
    mobilePanelOpen: boolean;
    mobileTab: string;
    rightView: string;
    current: any | null;
    accounts: any[];
    onlineNames: Set<string>;
    connected: boolean;
    connectingLabel: string;
    search: string;
    filtered: any[];
    groups: Record<string, string[]>;
    curGroup: string;
    avatarFailed: Set<string>;
    appVersion: string;
    progress: { done: number; total: number; label: string };
    logs: any[];
    themeMode: string;
    onSearch: () => void;
    onSelectGroup: (g: string) => void;
    onCreateGroup: () => void;
    onOpenAddAccount: () => void;
    onSelectAccount: (a: any) => void;
    avatarUrl: (a: any) => string;
    avatarColor: (name: string) => string;
    onAvatarError: (name: string) => void;
    onSwitch: (a: any) => void;
    onConnect: (a: any) => void;
    onLaunchClient: () => void;
    onOpenAccountFolder: () => void;
    onDisconnect: () => void;
    onReconnect: () => void;
    onLoadProfile: () => void;
    onOpenPanel: (v: any) => void;
    onDeleteContacts: () => void;
    onDeleteDialogs: (choice: string) => void;
    onPack: () => void;
    onRefreshInfo: () => void;
    onReloadLogs: () => void;
    onLoadSettings: () => void;
    onToggleTheme: () => void;
  } = $props();
</script>

<div class="mobile-app">
  <header class="mobile-header">
    {#if mobilePanelOpen}
      <button class="mobile-back" aria-label="返回" onclick={() => (mobilePanelOpen = false)}>‹</button>
      <div class="mobile-heading">
        <strong>{PANEL_TITLES[rightView] || '详情'}</strong>
        <span>{current?.display || current?.name || '当前账号'}</span>
      </div>
      <span class="mobile-header-spacer"></span>
    {:else}
      <div class="mobile-brand-mark" aria-hidden="true">TG</div>
      <div class="mobile-heading">
        <strong>TG小号工具箱</strong>
        <span>{accounts.length} 个账号 · {onlineNames.size} 个在线</span>
      </div>
      <span class="mobile-conn" class:on={connected && !connectingLabel} aria-label={connectingLabel || (connected ? '已连接' : '未连接')}></span>
      <button class="mobile-add" aria-label="新建账号" title="新建账号" onclick={onOpenAddAccount}>＋</button>
    {/if}
  </header>

  {#if !mobilePanelOpen}
    <main class="mobile-main">
      {#key mobileTab}
      <div class="mobile-page">
      {#if mobileTab === 'accounts'}
        <div class="mobile-account-toolbar">
          <label class="mobile-search-wrap">
            <span aria-hidden="true">⌕</span>
            <input class="mobile-search" placeholder="搜索账号" bind:value={search} oninput={onSearch} />
            {#if search}<button class="mobile-clear" aria-label="清空搜索" onclick={() => { search = ''; onSearch(); }}>×</button>{/if}
          </label>
          <button class="mobile-filter" aria-label="新建分组" title="新建分组" onclick={onCreateGroup}>☷</button>
        </div>
        <div class="mobile-groups" aria-label="账号分组">
          {#each ['all', 'ungrouped', ...Object.keys(groups)] as g}
            <button class="mobile-group" class:active={curGroup === g} onclick={() => onSelectGroup(g)}>
              {g === 'all' ? '全部' : g === 'ungrouped' ? '未分组' : g}
            </button>
          {/each}
          <button class="mobile-group mobile-group-add" aria-label="新建分组" onclick={onCreateGroup}>＋</button>
        </div>
        <div class="mobile-list-heading">
          <strong>{curGroup === 'all' ? '所有账号' : curGroup === 'ungrouped' ? '未分组' : curGroup}</strong>
          <span>{filtered.length}</span>
        </div>
        {#if filtered.length}
          <ul class="mobile-account-list">
            {#each filtered as a, i (a.name)}
              <li class="mobile-account-row" style="--i:{i}">
                <button class="mobile-account-main" onclick={() => onSelectAccount(a)}>
                  <span class="mobile-avatar-wrap">
                    {#if a.avatar && !avatarFailed.has(a.name)}
                      <img class="mobile-avatar" src={avatarUrl(a)} alt="" onerror={() => onAvatarError(a.name)} />
                    {:else}
                      <span class="mobile-avatar" style="background:{avatarColor(a.name)}">{a.display?.[0] || a.username?.[0] || a.name[0] || '-'}</span>
                    {/if}
                    <i class="mobile-presence" class:online={onlineNames.has(a.name)}></i>
                  </span>
                  <span class="mobile-account-copy">
                    <span class="mobile-account-name">{a.display || a.name}</span>
                    <span class="mobile-account-sub">{a.username ? `@${a.username}` : a.phone ? `+${a.phone}` : a.state}</span>
                  </span>
                  {#if (a as any).poll_alive === false}<span class="mobile-state failed">失效</span>{:else if onlineNames.has(a.name)}<span class="mobile-state online">在线</span>{:else}<span class="mobile-state">离线</span>{/if}
                  <span class="mobile-chevron" aria-hidden="true">›</span>
                </button>
                <button class="mobile-row-connect" aria-label={onlineNames.has(a.name) ? `切换到${a.display || a.name}` : `连接${a.display || a.name}`} onclick={() => onlineNames.has(a.name) ? onSwitch(a) : onConnect(a)}>
                  {onlineNames.has(a.name) ? '切换' : '连接'}
                </button>
              </li>
            {/each}
          </ul>
        {:else}
          <div class="mobile-empty">
            <span class="mobile-empty-icon" aria-hidden="true">＋</span>
            <strong>{search ? '没有匹配的账号' : '还没有账号'}</strong>
            <span>{search ? '换个关键词试试' : '添加账号后即可在此管理连接与资料'}</span>
            {#if !search}<button class="mobile-primary" onclick={onOpenAddAccount}>新建账号</button>{/if}
          </div>
        {/if}
      {:else if mobileTab === 'current'}
        {#if current}
          <section class="mobile-current-card">
            <div class="mobile-current-top">
              <span class="mobile-current-avatar" style="background:{avatarColor(current.name)}">
                {#if current.avatar && !avatarFailed.has(current.name)}
                  <img src={avatarUrl(current)} alt="" onerror={() => onAvatarError(current.name)} />
                {:else}{current.display?.[0] || current.name[0] || '-'}{/if}
              </span>
              <div class="mobile-current-copy">
                <strong>{current.display || current.name}</strong>
                <span>{current.username ? `@${current.username}` : current.phone ? `+${current.phone}` : current.name}</span>
                <span class="mobile-current-status" class:online={onlineNames.has(current.name)}>
                  <i></i>{onlineNames.has(current.name) ? '已连接' : connectingLabel || '未连接'}
                </span>
              </div>
              <button class="mobile-more-action" aria-label="账号操作" title="账号操作" onclick={onOpenAccountFolder}>•••</button>
            </div>
            <div class="mobile-primary-actions">
              {#if onlineNames.has(current.name)}
                <button class="mobile-primary" onclick={onDisconnect}>断开连接</button>
                <button class="mobile-secondary" onclick={onReconnect}>重新连接</button>
              {:else}
                <button class="mobile-primary" onclick={() => onConnect(current)}>连接账号</button>
                <button class="mobile-secondary" onclick={onLaunchClient}>启动客户端</button>
              {/if}
            </div>
          </section>
          <div class="mobile-section-label">账号管理</div>
          <div class="mobile-action-list">
            <button onclick={onLoadProfile}><span class="mobile-action-icon mint">人</span><span><strong>个人资料</strong><small>姓名、用户名、头像与生日</small></span><b>›</b></button>
            <button onclick={() => onOpenPanel('chat')}><span class="mobile-action-icon blue">聊</span><span><strong>消息与会话</strong><small>查看会话、收发消息</small></span><b>›</b></button>
            <button onclick={() => onOpenPanel('2fa')}><span class="mobile-action-icon violet">盾</span><span><strong>安全设置</strong><small>两步验证、通行密钥与设备</small></span><b>›</b></button>
            <button onclick={() => onOpenPanel('devices')}><span class="mobile-action-icon amber">端</span><span><strong>登录设备</strong><small>查看并管理已授权设备</small></span><b>›</b></button>
          </div>
          <div class="mobile-section-label">常用操作</div>
          <div class="mobile-quick-grid">
            <button onclick={onDeleteContacts}><span>删</span><strong>删联系人</strong></button>
            <button onclick={() => onDeleteDialogs('users')}><span>清</span><strong>删对话</strong></button>
            <button onclick={onPack}><span>包</span><strong>打包账号</strong></button>
            <button onclick={onRefreshInfo}><span>刷</span><strong>刷新资料</strong></button>
          </div>
        {:else}
          <div class="mobile-empty">
            <span class="mobile-empty-icon" aria-hidden="true">◎</span>
            <strong>尚未选择账号</strong>
            <span>先从账号列表中选择或连接一个账号</span>
            <button class="mobile-primary" onclick={() => (mobileTab = 'accounts')}>查看账号</button>
          </div>
        {/if}
      {:else if mobileTab === 'activity'}
        <div class="mobile-activity-head">
          <div><strong>运行记录</strong><span>最近的连接与操作状态</span></div>
          <button class="mobile-refresh" aria-label="刷新日志" title="刷新日志" onclick={onReloadLogs}>↻</button>
        </div>
        {#if progress.label}
          <div class="mobile-progress"><span>{progress.label}</span><b>{progress.done}/{progress.total}</b><div><i style="width:{progress.total ? Math.min(100, Math.round(progress.done / progress.total * 100)) : 0}%"></i></div></div>
        {/if}
        {#if logs.length}
          <ul class="mobile-log-list">
            {#each logs as e, i (e.ts + '|' + i)}
              <li class:error={e.level === 'error'} class:warning={e.level === 'warn'}>
                <i></i><div><span>{e.msg}</span><time>{e.ts ? e.ts.slice(11, 19) : ''}</time></div>
              </li>
            {/each}
          </ul>
        {:else}
          <div class="mobile-empty compact"><strong>暂无运行记录</strong><span>连接账号或执行操作后，状态会显示在这里</span></div>
        {/if}
      {:else}
        <div class="mobile-section-label">偏好设置</div>
        <div class="mobile-action-list">
          <button onclick={onLoadSettings}><span class="mobile-action-icon blue">设</span><span><strong>程序设置</strong><small>外观、代理、白名单与打包</small></span><b>›</b></button>
          <button onclick={onToggleTheme}><span class="mobile-action-icon violet">◐</span><span><strong>切换外观</strong><small>当前：{themeMode === 'dark' ? '深色' : '浅色'}</small></span><b>›</b></button>
          <button onclick={() => onOpenPanel('join')}><span class="mobile-action-icon mint">群</span><span><strong>群组与频道</strong><small>管理常用加入链接</small></span><b>›</b></button>
          <button onclick={onOpenAddAccount}><span class="mobile-action-icon amber">＋</span><span><strong>新建账号</strong><small>导入文件或扫码登录</small></span><b>›</b></button>
          <button onclick={() => onOpenPanel('log')}><span class="mobile-action-icon slate">≡</span><span><strong>运行日志</strong><small>查看程序状态与错误</small></span><b>›</b></button>
        </div>
        <div class="mobile-version">TG小号工具箱{appVersion ? ` · v${appVersion}` : ''}</div>
      {/if}
      </div>
      {/key}
    </main>
  {/if}

  <nav class="mobile-nav" aria-label="主导航">
    <button class:active={mobileTab === 'accounts' && !mobilePanelOpen} aria-current={mobileTab === 'accounts' && !mobilePanelOpen ? 'page' : undefined} onclick={() => { mobilePanelOpen = false; mobileTab = 'accounts'; }}><span aria-hidden="true">▦</span><small>账号</small></button>
    <button class:active={mobileTab === 'current' && !mobilePanelOpen} aria-current={mobileTab === 'current' && !mobilePanelOpen ? 'page' : undefined} onclick={() => { mobilePanelOpen = false; mobileTab = 'current'; }}><span aria-hidden="true">◉</span><small>当前</small></button>
    <button class:active={mobileTab === 'activity' && !mobilePanelOpen} aria-current={mobileTab === 'activity' && !mobilePanelOpen ? 'page' : undefined} onclick={() => { mobilePanelOpen = false; mobileTab = 'activity'; }}><span aria-hidden="true">≡</span><small>动态</small></button>
    <button class:active={mobileTab === 'more' && !mobilePanelOpen} aria-current={mobileTab === 'more' && !mobilePanelOpen ? 'page' : undefined} onclick={() => { mobilePanelOpen = false; mobileTab = 'more'; }}><span aria-hidden="true">•••</span><small>更多</small></button>
  </nav>
</div>
