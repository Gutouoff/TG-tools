<script lang="ts">
  import { t } from '../texts';

  const PANEL_TITLES: Record<string, string> = {
    log: t('mob.panel.log'),
    chat: t('mob.panel.chat'),
    profile: t('mob.panel.profile'),
    passkey: t('mob.panel.passkey'),
    '2fa': t('mob.panel.2fa'),
    email: t('mob.panel.email'),
    devices: t('mob.panel.devices'),
    join: t('mob.panel.join'),
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
      <button class="mobile-back" aria-label={t('mob.back')} onclick={() => (mobilePanelOpen = false)}>‹</button>
      <div class="mobile-heading">
        <strong>{PANEL_TITLES[rightView] || t('mob.detail')}</strong>
        <span>{current?.display || current?.name || t('mob.currentAccount')}</span>
      </div>
      <span class="mobile-header-spacer"></span>
    {:else}
      <div class="mobile-brand-mark" aria-hidden="true">TG</div>
      <div class="mobile-heading">
        <strong>{t('mob.title')}</strong>
        <span>{t('mob.subtitle', { accounts: accounts.length, online: onlineNames.size })}</span>
      </div>
      <span class="mobile-conn" class:on={connected && !connectingLabel} aria-label={connectingLabel || (connected ? t('mob.connected') : t('mob.disconnected'))}></span>
      <button class="mobile-add" aria-label={t('mob.newAccount')} title={t('mob.newAccount')} onclick={onOpenAddAccount}>＋</button>
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
            <input class="mobile-search" placeholder={t('mob.search')} bind:value={search} oninput={onSearch} />
            {#if search}<button class="mobile-clear" aria-label={t('mob.clearSearch')} onclick={() => { search = ''; onSearch(); }}>×</button>{/if}
          </label>
          <button class="mobile-filter" aria-label={t('mob.newGroup')} title={t('mob.newGroup')} onclick={onCreateGroup}>☷</button>
        </div>
        <div class="mobile-groups" aria-label={t('mob.groupsAria')}>
          {#each ['all', 'ungrouped', ...Object.keys(groups)] as g}
            <button class="mobile-group" class:active={curGroup === g} onclick={() => onSelectGroup(g)}>
              {g === 'all' ? t('mob.all') : g === 'ungrouped' ? t('mob.ungrouped') : g}
            </button>
          {/each}
          <button class="mobile-group mobile-group-add" aria-label={t('mob.newGroup')} onclick={onCreateGroup}>＋</button>
        </div>
        <div class="mobile-list-heading">
          <strong>{curGroup === 'all' ? t('mob.allAccounts') : curGroup === 'ungrouped' ? t('mob.ungrouped') : curGroup}</strong>
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
                  {#if (a as any).poll_alive === false}<span class="mobile-state failed">{t('mob.failed')}</span>{:else if onlineNames.has(a.name)}<span class="mobile-state online">{t('mob.online')}</span>{:else}<span class="mobile-state">{t('mob.offline')}</span>{/if}
                  <span class="mobile-chevron" aria-hidden="true">›</span>
                </button>
                <button class="mobile-row-connect" aria-label={onlineNames.has(a.name) ? t('mob.switchTo', { name: a.display || a.name }) : t('mob.connectTo', { name: a.display || a.name })} onclick={() => onlineNames.has(a.name) ? onSwitch(a) : onConnect(a)}>
                  {onlineNames.has(a.name) ? t('mob.switch') : t('mob.connect')}
                </button>
              </li>
            {/each}
          </ul>
        {:else}
          <div class="mobile-empty">
            <span class="mobile-empty-icon" aria-hidden="true">＋</span>
            <strong>{search ? t('mob.noMatch') : t('mob.noAccounts')}</strong>
            <span>{search ? t('mob.tryOther') : t('mob.addHint')}</span>
            {#if !search}<button class="mobile-primary" onclick={onOpenAddAccount}>{t('mob.newAccount')}</button>{/if}
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
                  <i></i>{onlineNames.has(current.name) ? t('mob.connected') : connectingLabel || t('mob.disconnected')}
                </span>
              </div>
              <button class="mobile-more-action" aria-label={t('mob.accountOps')} title={t('mob.accountOps')} onclick={onOpenAccountFolder}>•••</button>
            </div>
            <div class="mobile-primary-actions">
              {#if onlineNames.has(current.name)}
                <button class="mobile-primary" onclick={onDisconnect}>{t('mob.disconnect')}</button>
                <button class="mobile-secondary" onclick={onReconnect}>{t('mob.reconnect')}</button>
              {:else}
                <button class="mobile-primary" onclick={() => onConnect(current)}>{t('mob.connectAccount')}</button>
                <button class="mobile-secondary" onclick={onLaunchClient}>{t('mob.launchClient')}</button>
              {/if}
            </div>
          </section>
          <div class="mobile-section-label">{t('mob.sectAccounts')}</div>
          <div class="mobile-action-list">
            <button onclick={onLoadProfile}><span class="mobile-action-icon mint">人</span><span><strong>{t('mob.profile')}</strong><small>{t('mob.profileHint')}</small></span><b>›</b></button>
            <button onclick={() => onOpenPanel('chat')}><span class="mobile-action-icon blue">聊</span><span><strong>{t('mob.messages')}</strong><small>{t('mob.messagesHint')}</small></span><b>›</b></button>
            <button onclick={() => onOpenPanel('2fa')}><span class="mobile-action-icon violet">盾</span><span><strong>{t('mob.security')}</strong><small>{t('mob.securityHint')}</small></span><b>›</b></button>
            <button onclick={() => onOpenPanel('devices')}><span class="mobile-action-icon amber">端</span><span><strong>{t('mob.devices')}</strong><small>{t('mob.devicesHint')}</small></span><b>›</b></button>
          </div>
          <div class="mobile-section-label">{t('mob.sectActions')}</div>
          <div class="mobile-quick-grid">
            <button onclick={onDeleteContacts}><span>删</span><strong>{t('mob.delContacts')}</strong></button>
            <button onclick={() => onDeleteDialogs('users')}><span>清</span><strong>{t('mob.delDialogs')}</strong></button>
            <button onclick={onPack}><span>包</span><strong>{t('mob.pack')}</strong></button>
            <button onclick={onRefreshInfo}><span>刷</span><strong>{t('mob.refreshInfo')}</strong></button>
          </div>
        {:else}
          <div class="mobile-empty">
            <span class="mobile-empty-icon" aria-hidden="true">◎</span>
            <strong>{t('mob.noSelection')}</strong>
            <span>{t('mob.selectHint')}</span>
            <button class="mobile-primary" onclick={() => (mobileTab = 'accounts')}>{t('mob.viewAccounts')}</button>
          </div>
        {/if}
      {:else if mobileTab === 'activity'}
        <div class="mobile-activity-head">
          <div><strong>{t('mob.activity')}</strong><span>{t('mob.activityHint')}</span></div>
          <button class="mobile-refresh" aria-label={t('mob.reloadLogs')} title={t('mob.reloadLogs')} onclick={onReloadLogs}>↻</button>
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
          <div class="mobile-empty compact"><strong>{t('mob.noActivity')}</strong><span>{t('mob.activityEmpty')}</span></div>
        {/if}
      {:else}
        <div class="mobile-section-label">{t('mob.sectPrefs')}</div>
        <div class="mobile-action-list">
          <button onclick={onLoadSettings}><span class="mobile-action-icon blue">设</span><span><strong>{t('mob.settings')}</strong><small>{t('mob.settingsHint')}</small></span><b>›</b></button>
          <button onclick={onToggleTheme}><span class="mobile-action-icon violet">◐</span><span><strong>{t('mob.theme')}</strong><small>{t('mob.themeHint', { mode: themeMode === 'dark' ? t('mob.themeDark') : t('mob.themeLight') })}</small></span><b>›</b></button>
          <button onclick={() => onOpenPanel('join')}><span class="mobile-action-icon mint">群</span><span><strong>{t('mob.join')}</strong><small>{t('mob.joinHint')}</small></span><b>›</b></button>
          <button onclick={onOpenAddAccount}><span class="mobile-action-icon amber">＋</span><span><strong>{t('mob.newAccount')}</strong><small>{t('mob.addHintShort')}</small></span><b>›</b></button>
          <button onclick={() => onOpenPanel('log')}><span class="mobile-action-icon slate">≡</span><span><strong>{t('mob.logs')}</strong><small>{t('mob.logsHint')}</small></span><b>›</b></button>
        </div>
        <div class="mobile-version">{t('mob.title')}{appVersion ? ` · v${appVersion}` : ''}</div>
      {/if}
      </div>
      {/key}
    </main>
  {/if}

  <nav class="mobile-nav" aria-label={t('mob.navAria')}>
    <button class:active={mobileTab === 'accounts' && !mobilePanelOpen} aria-current={mobileTab === 'accounts' && !mobilePanelOpen ? 'page' : undefined} onclick={() => { mobilePanelOpen = false; mobileTab = 'accounts'; }}><span aria-hidden="true">▦</span><small>{t('mob.tabAccounts')}</small></button>
    <button class:active={mobileTab === 'current' && !mobilePanelOpen} aria-current={mobileTab === 'current' && !mobilePanelOpen ? 'page' : undefined} onclick={() => { mobilePanelOpen = false; mobileTab = 'current'; }}><span aria-hidden="true">◉</span><small>{t('mob.tabCurrent')}</small></button>
    <button class:active={mobileTab === 'activity' && !mobilePanelOpen} aria-current={mobileTab === 'activity' && !mobilePanelOpen ? 'page' : undefined} onclick={() => { mobilePanelOpen = false; mobileTab = 'activity'; }}><span aria-hidden="true">≡</span><small>{t('mob.tabActivity')}</small></button>
    <button class:active={mobileTab === 'more' && !mobilePanelOpen} aria-current={mobileTab === 'more' && !mobilePanelOpen ? 'page' : undefined} onclick={() => { mobilePanelOpen = false; mobileTab = 'more'; }}><span aria-hidden="true">•••</span><small>{t('mob.tabMore')}</small></button>
  </nav>
</div>
