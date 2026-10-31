<script lang="ts">
  import { t } from '../texts';

  let {
    section = $bindable('general'),
    mobileSection = $bindable(null),
    themeMode,
    appVersion,
    settings,
    joinEntries,
    emailPresets = $bindable([]),
    wlUsers,
    wlGroups,
    wlUserInput = $bindable(''),
    wlGroupInput = $bindable(''),
    cardOrder,
    moveCard,
    renameQuickDefs,
    toggleRenameQuick,
    presetColors,
    applyPreset,
    isPreset,
    applyTheme,
    setThemeMode,
    settingsInfo,
    openSettingsSection,
    doAddUser,
    doRemoveUser,
    doAddGroup,
    doRemoveGroup,
    onLoadWhitelist,
    onOpenJoinManager,
    onSave,
    onClose,
  }: {
    section: string;
    mobileSection: string | null;
    themeMode: string;
    appVersion: string;
    settings: any;
    joinEntries: any[];
    emailPresets: string[];
    wlUsers: number[];
    wlGroups: number[];
    wlUserInput: string;
    wlGroupInput: string;
    cardOrder: string[];
    moveCard: (i: number, dir: number) => void;
    renameQuickDefs: Array<[string, string]>;
    toggleRenameQuick: (key: string) => void;
    presetColors: string[];
    applyPreset: (c: string) => void;
    isPreset: () => boolean;
    applyTheme: () => void;
    setThemeMode: (mode: string) => void;
    settingsInfo: () => { icon: string; title: string; description: string };
    openSettingsSection: (s: any) => void;
    doAddUser: () => void;
    doRemoveUser: (id: number) => void;
    doAddGroup: () => void;
    doRemoveGroup: (id: number) => void;
    onLoadWhitelist: () => void;
    onOpenJoinManager: () => void;
    onSave: () => void;
    onClose: () => void;
  } = $props();
</script>

<div class="modal-mask" onclick={onClose}>
  <div class="modal settings-modal" class:set-mobile-sub={mobileSection !== null} onclick={(e) => e.stopPropagation()}>
    <div class="set-mobile-head">
      {#if mobileSection !== null}
        <button class="set-mobile-back" aria-label={t('set.backAria')} onclick={() => (mobileSection = null)}>‹</button>
      {/if}
      <strong>{mobileSection !== null ? settingsInfo().title : t('set.title')}</strong>
      <button class="set-mobile-close" aria-label={t('set.closeAria')} onclick={() => { onClose(); mobileSection = null; }}>✕</button>
    </div>
    <div class="set-mobile-root">
      <div class="set-mobile-group-label">{t('set.navConfig')}</div>
      <div class="set-mobile-group">
        <button onclick={() => openSettingsSection('general')}>
          <span class="set-mobile-ico">⚙</span>
          <span class="set-mobile-copy"><strong>{t('set.navGeneral')}</strong><small>{t('set.generalDesc')}</small></span>
          <span class="set-mobile-value">{settings.log_level === 'debug' ? t('set.logLevelDebug') : t('set.logLevelInfo')}</span>
          <b aria-hidden="true">›</b>
        </button>
        <button onclick={() => openSettingsSection('appearance')}>
          <span class="set-mobile-ico">◐</span>
          <span class="set-mobile-copy"><strong>{t('set.navAppearance')}</strong><small>{t('set.appearanceDesc')}</small></span>
          <span class="set-mobile-value">{themeMode === 'dark' ? t('set.themeDark') : t('set.themeLight')}</span>
          <b aria-hidden="true">›</b>
        </button>
        <button onclick={() => openSettingsSection('proxy')}>
          <span class="set-mobile-ico">⇄</span>
          <span class="set-mobile-copy"><strong>{t('set.navProxy')}</strong><small>{t('set.proxyDesc')}</small></span>
          <span class="set-mobile-value">{settings.proxy_mode && settings.proxy_mode !== 'none' ? `${settings.proxy_host || t('set.proxyConfigured')}:${settings.proxy_port || ''}` : t('set.proxyDisabled')}</span>
          <b aria-hidden="true">›</b>
        </button>
      </div>

      <div class="set-mobile-group-label">{t('set.navTools')}</div>
      <div class="set-mobile-group">
        <button onclick={() => openSettingsSection('join')}>
          <span class="set-mobile-ico">↗</span>
          <span class="set-mobile-copy"><strong>{t('set.navJoin')}</strong><small>{t('set.joinDesc')}</small></span>
          <span class="set-mobile-value">{t('set.countJoin', { n: joinEntries.length })}</span>
          <b aria-hidden="true">›</b>
        </button>
        <button onclick={() => openSettingsSection('whitelist')}>
          <span class="set-mobile-ico">✓</span>
          <span class="set-mobile-copy"><strong>{t('set.navWhitelist')}</strong><small>{t('set.whitelistDesc')}</small></span>
          <span class="set-mobile-value">{t('set.countWhitelist', { n: wlUsers.length + wlGroups.length })}</span>
          <b aria-hidden="true">›</b>
        </button>
      </div>

      <div class="set-mobile-group-label">{t('set.navHelp')}</div>
      <div class="set-mobile-group">
        <button onclick={() => openSettingsSection('about')}>
          <span class="set-mobile-ico">i</span>
          <span class="set-mobile-copy"><strong>{t('set.navAbout')}</strong><small>{t('set.aboutDesc')}</small></span>
          <span class="set-mobile-value">v{appVersion || '…'}</span>
          <b aria-hidden="true">›</b>
        </button>
      </div>
    </div>
    <nav class="set-nav" aria-label={t('set.navAria')}>
      <div class="set-nav-brand">
        <div class="set-nav-brand-mark">TG</div>
        <div><strong>{t('set.brandTitle')}</strong><span>{t('set.brandSub')}</span></div>
      </div>
      <div class="set-nav-label">{t('set.navConfig')}</div>
      <button class="set-nav-item" class:on={section === 'general'} onclick={() => (section = 'general')}><span class="set-nav-icon">⚙</span><span>{t('set.navGeneral')}</span></button>
      <button class="set-nav-item" class:on={section === 'appearance'} onclick={() => (section = 'appearance')}><span class="set-nav-icon">◐</span><span>{t('set.navAppearance')}</span></button>
      <button class="set-nav-item" class:on={section === 'proxy'} onclick={() => (section = 'proxy')}><span class="set-nav-icon">⇄</span><span>{t('set.navProxy')}</span></button>
      <div class="set-nav-label">{t('set.navTools')}</div>
      <button class="set-nav-item" class:on={section === 'join'} onclick={() => (section = 'join')}><span class="set-nav-icon">↗</span><span>{t('set.navJoin')}</span></button>
      <div class="set-nav-label">{t('set.navProtection')}</div>
      <button class="set-nav-item" class:on={section === 'whitelist'} onclick={() => { section = 'whitelist'; onLoadWhitelist(); }}><span class="set-nav-icon">✓</span><span>{t('set.navWhitelist')}</span></button>
      <div class="set-nav-spacer"></div>
      <div class="set-nav-label">{t('set.navHelp')}</div>
      <button class="set-nav-item" class:on={section === 'about'} onclick={() => (section = 'about')}><span class="set-nav-icon">i</span><span>{t('set.navAbout')}</span></button>
    </nav>
    <main class="set-content">
      <div class="set-heading">
        <div class="set-heading-icon">{settingsInfo().icon}</div>
        <div class="set-heading-copy">
          <h1>{settingsInfo().title}</h1>
          <p>{settingsInfo().description}</p>
        </div>
      </div>
      <div class="set-content-body">
      {#if section === 'general'}
        <div class="set-sec-title">{t('set.navGeneral')}</div>
        <div class="set-group">
          <div class="set-row">
            <span class="set-label">{t('set.general.packNaming')}</span>
            <input class="set-input" bind:value={settings.pack_naming} placeholder={t('set.general.packNamingPlaceholder')} />
          </div>
          <div class="set-row">
            <span class="set-label">{t('set.general.packPassword')}</span>
            <input class="set-input" type="password" autocomplete="new-password" bind:value={settings.pack_password} placeholder={t('set.general.packPasswordPlaceholder')} />
          </div>
          <div class="set-row">
            <span class="set-label">{t('set.general.logLevel')}</span>
            <select class="set-select" bind:value={settings.log_level}>
              <option value="info">{t('set.general.logInfo')}</option>
              <option value="debug">{t('set.general.logDebug')}</option>
            </select>
          </div>
          <div class="set-row set-row-col">
            <span class="set-label">{t('set.general.renameQuick')}</span>
            <div class="check-row">
              {#each renameQuickDefs as [k, label]}
                <label class="check-item">
                  <input
                    type="checkbox"
                    checked={((settings.rename_quick as string[]) || []).includes(k)}
                    onchange={() => toggleRenameQuick(k)}
                  />
                  <span>{label}</span>
                </label>
              {/each}
            </div>
          </div>
          <div class="set-row">
            <span class="set-label">{t('set.general.renamePrefix')}</span>
            <input class="set-input" bind:value={settings.rename_prefix} placeholder={t('set.general.renamePrefixPlaceholder')} title={t('set.general.renamePrefixTitle')} />
          </div>
        </div>
      {:else if section === 'appearance'}
        <div class="set-sec-title">{t('set.navAppearance')}</div>
        <div class="set-group">
          <div class="mode-seg">
            <button class="mode-item" class:on={themeMode === 'light'} title={t('set.themeLight')} onclick={() => setThemeMode('light')}>
              {#if themeMode === 'light'}✓{/if} ☀️ {t('set.themeLight')}
            </button>
            <button class="mode-item" class:on={themeMode === 'dark'} title={t('set.themeDark')} onclick={() => setThemeMode('dark')}>
              {#if themeMode === 'dark'}✓{/if} 🌙 {t('set.themeDark')}
            </button>
          </div>
        </div>
        <div class="set-group-title">{t('set.appearance.colors')}</div>
        <div class="set-group">
          <div class="swatch-grid">
            {#each presetColors as c (c)}
              <button
                class="swatch"
                class:on={((settings.theme_seed as string) || '').toLowerCase() === c.toLowerCase()}
                style="--sw:{c};--sw-light:color-mix(in srgb, {c} 55%, white)"
                title={c}
                onclick={() => applyPreset(c)}
              ></button>
            {/each}
            <label class="swatch custom" class:on={!isPreset()} title={t('set.appearance.custom')}>
              🖌️
              <input type="color" bind:value={settings.theme_seed} onchange={() => applyTheme()} />
            </label>
          </div>
        </div>
        <div class="set-group-title">{t('set.appearance.detail')}</div>
        <div class="set-group">
          <div class="set-row">
            <span class="set-label">{t('set.appearance.bgLight')}</span>
            <input class="set-color" type="color" bind:value={settings.theme_bg} onchange={() => applyTheme()} />
          </div>
          <div class="set-row">
            <span class="set-label">{t('set.appearance.bgDark')}</span>
            <input class="set-color" type="color" bind:value={settings.theme_dark} onchange={() => applyTheme()} />
          </div>
          <div class="set-row">
            <span class="set-label">{t('set.appearance.topbar')}</span>
            <input class="set-color" type="color" bind:value={settings.theme_topbar} onchange={() => applyTheme()} />
          </div>
        </div>
        <div class="set-group-title">{t('set.appearance.order')}</div>
        <div class="set-group">
          {#each cardOrder as c, i (c)}
            <div class="set-row">
              <span class="set-label">{c}</span>
              <span class="order-btns">
                <button class="order-btn" disabled={i === 0} title={t('set.appearance.moveUp')} onclick={() => moveCard(i, -1)}>↑</button>
                <button class="order-btn" disabled={i === cardOrder.length - 1} title={t('set.appearance.moveDown')} onclick={() => moveCard(i, 1)}>↓</button>
              </span>
            </div>
          {/each}
        </div>
      {:else if section === 'proxy'}
        <div class="set-sec-title">{t('set.navProxy')}</div>
        <div class="set-group">
          <div class="set-row">
            <span class="set-label">{t('set.proxy.mode')}</span>
            <select class="set-select" bind:value={settings.proxy_mode}>
              <option value="none">{t('set.proxy.modeNone')}</option>
              <option value="system">{t('set.proxy.modeSystem')}</option>
              <option value="manual">{t('set.proxy.modeManual')}</option>
            </select>
          </div>
          {#if settings.proxy_mode === 'manual'}
            <div class="set-row">
              <span class="set-label">{t('set.proxy.scheme')}</span>
              <select class="set-select" bind:value={settings.proxy_scheme}>
                <option value="socks5">SOCKS5</option>
                <option value="socks4">SOCKS4</option>
                <option value="http">HTTP</option>
              </select>
            </div>
            <div class="set-row">
              <span class="set-label">{t('set.proxy.host')}</span>
              <input class="set-input" bind:value={settings.proxy_host} placeholder="127.0.0.1" />
            </div>
            <div class="set-row">
              <span class="set-label">{t('set.proxy.port')}</span>
              <input class="set-input" bind:value={settings.proxy_port} placeholder="7890" />
            </div>
          {/if}
        </div>
      {:else if section === 'join'}
        <section class="settings-card join-email-card">
          <div class="settings-card-head">
            <div class="settings-card-icon">@</div>
            <div>
              <h2>{t('set.join.emailTitle')}</h2>
              <p>{t('set.join.emailDesc')}</p>
            </div>
            <span class="settings-card-count">{t('set.countJoin', { n: emailPresets.length })}</span>
          </div>
          <div class="settings-card-body">
            {#each emailPresets as p, i}
              <div class="join-edit-row email-row">
                <span class="row-index">{String(i + 1).padStart(2, '0')}</span>
                <input class="set-input join-link" bind:value={emailPresets[i]} placeholder={t('set.join.emailPlaceholder')} />
                <button class="order-btn row-delete" title={t('set.join.deleteRow')} aria-label={t('set.join.deleteRow')} onclick={() => emailPresets.splice(i, 1)}>×</button>
              </div>
            {/each}
            {#if !emailPresets.length}
              <div class="settings-empty">
                <div class="settings-empty-icon">@</div>
                <strong>{t('set.join.emailEmpty')}</strong>
                <span>{t('set.join.emailEmptyHint')}</span>
              </div>
            {/if}
            <md-outlined-button class="add-setting-btn" onclick={() => emailPresets = [...emailPresets, '']}>＋ {t('set.join.addEmail')}</md-outlined-button>
          </div>
        </section>
        <section class="settings-card join-link-card">
          <div class="settings-card-head">
            <div class="settings-card-icon">↗</div>
            <div>
              <h2>{t('set.navJoin')}</h2>
              <p>{t('set.join.linkDesc')}</p>
            </div>
          </div>
          <div class="settings-card-action">
            <span>{t('set.join.goManage')}</span>
            <md-outlined-button onclick={onOpenJoinManager}>{t('set.join.openManage')} <span aria-hidden="true">→</span></md-outlined-button>
          </div>
        </section>
      {:else if section === 'whitelist'}
        <div class="set-sec-title">{t('set.navWhitelist')}</div>
        <p class="set-hint">{t('set.whitelist.hint')}</p>
        <div class="set-group-title">{t('set.whitelist.users')}</div>
        <div class="set-group">
          <div class="join-edit-row">
            <input class="set-input join-link" placeholder={t('set.whitelist.userPlaceholder')} bind:value={wlUserInput} />
            <md-outlined-button onclick={doAddUser}>{t('set.whitelist.add')}</md-outlined-button>
          </div>
          <ul class="sec-list">
            {#each wlUsers as u}
              <li class="sec-item"><span>{u}</span><button class="danger" onclick={() => doRemoveUser(u)}>{t('set.whitelist.remove')}</button></li>
            {/each}
          </ul>
        </div>
        <div class="set-group-title">{t('set.whitelist.groups')}</div>
        <div class="set-group">
          <div class="join-edit-row">
            <input class="set-input join-link" placeholder={t('set.whitelist.groupPlaceholder')} bind:value={wlGroupInput} />
            <md-outlined-button onclick={doAddGroup}>{t('set.whitelist.add')}</md-outlined-button>
          </div>
          <ul class="sec-list">
            {#each wlGroups as g}
              <li class="sec-item"><span>{g}</span><button class="danger" onclick={() => doRemoveGroup(g)}>{t('set.whitelist.remove')}</button></li>
            {/each}
          </ul>
        </div>
      {:else if section === 'about'}
        <div class="set-sec-title">{t('set.navAbout')}</div>
        <div class="about-list">
          <div class="about-row"><span class="set-label">{t('set.about.name')}</span><span>{t('set.about.appName')}</span></div>
          <div class="about-row"><span class="set-label">{t('set.about.version')}</span><span class="about-ver">v{appVersion || '…'}</span></div>
          <div class="about-row"><span class="set-label">{t('set.about.repo')}</span><span>github.com/Gutouoff/TG-tools</span></div>
        </div>
      {:else}
        <div class="set-sec-title">{t('set.navGeneral')}</div>
      {/if}
      </div>
      <div class="set-footer">
        <md-filled-button onclick={onSave}>{t('set.save')}</md-filled-button>
      </div>
    </main>
    <button class="back set-close" title={t('common.close')} onclick={onClose}>✕</button>
  </div>
</div>
