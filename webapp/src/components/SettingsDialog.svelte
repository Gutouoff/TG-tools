<script lang="ts">
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
        <button class="set-mobile-back" aria-label="返回设置列表" onclick={() => (mobileSection = null)}>‹</button>
      {/if}
      <strong>{mobileSection !== null ? settingsInfo().title : '设置'}</strong>
      <button class="set-mobile-close" aria-label="关闭设置" onclick={() => { onClose(); mobileSection = null; }}>✕</button>
    </div>
    <div class="set-mobile-root">
      <div class="set-mobile-group-label">配置</div>
      <div class="set-mobile-group">
        <button onclick={() => openSettingsSection('general')}>
          <span class="set-mobile-ico">⚙</span>
          <span class="set-mobile-copy"><strong>通用</strong><small>打包命名、压缩密码、日志等级</small></span>
          <span class="set-mobile-value">{settings.log_level === 'debug' ? '调试' : '常规'}</span>
          <b aria-hidden="true">›</b>
        </button>
        <button onclick={() => openSettingsSection('appearance')}>
          <span class="set-mobile-ico">◐</span>
          <span class="set-mobile-copy"><strong>外观</strong><small>界面模式与色彩主题</small></span>
          <span class="set-mobile-value">{themeMode === 'dark' ? '深色' : '浅色'}</span>
          <b aria-hidden="true">›</b>
        </button>
        <button onclick={() => openSettingsSection('proxy')}>
          <span class="set-mobile-ico">⇄</span>
          <span class="set-mobile-copy"><strong>代理</strong><small>Telegram 连接使用的网络代理</small></span>
          <span class="set-mobile-value">{settings.proxy_mode && settings.proxy_mode !== 'none' ? `${settings.proxy_host || '已配置'}:${settings.proxy_port || ''}` : '未启用'}</span>
          <b aria-hidden="true">›</b>
        </button>
      </div>

      <div class="set-mobile-group-label">工具</div>
      <div class="set-mobile-group">
        <button onclick={() => openSettingsSection('join')}>
          <span class="set-mobile-ico">↗</span>
          <span class="set-mobile-copy"><strong>加群频道</strong><small>常用群组与频道链接</small></span>
          <span class="set-mobile-value">{joinEntries.length} 个</span>
          <b aria-hidden="true">›</b>
        </button>
        <button onclick={() => openSettingsSection('whitelist')}>
          <span class="set-mobile-ico">✓</span>
          <span class="set-mobile-copy"><strong>白名单</strong><small>删除时永久保留的对象</small></span>
          <span class="set-mobile-value">{wlUsers.length + wlGroups.length} 项</span>
          <b aria-hidden="true">›</b>
        </button>
      </div>

      <div class="set-mobile-group-label">帮助</div>
      <div class="set-mobile-group">
        <button onclick={() => openSettingsSection('about')}>
          <span class="set-mobile-ico">i</span>
          <span class="set-mobile-copy"><strong>关于</strong><small>版本与仓库地址</small></span>
          <span class="set-mobile-value">v{appVersion || '…'}</span>
          <b aria-hidden="true">›</b>
        </button>
      </div>
    </div>
    <nav class="set-nav" aria-label="设置导航">
      <div class="set-nav-brand">
        <div class="set-nav-brand-mark">TG</div>
        <div><strong>工具箱设置</strong><span>偏好与连接</span></div>
      </div>
      <div class="set-nav-label">配置</div>
      <button class="set-nav-item" class:on={section === 'general'} onclick={() => (section = 'general')}><span class="set-nav-icon">⚙</span><span>通用</span></button>
      <button class="set-nav-item" class:on={section === 'appearance'} onclick={() => (section = 'appearance')}><span class="set-nav-icon">◐</span><span>外观</span></button>
      <button class="set-nav-item" class:on={section === 'proxy'} onclick={() => (section = 'proxy')}><span class="set-nav-icon">⇄</span><span>代理</span></button>
      <div class="set-nav-label">工具</div>
      <button class="set-nav-item" class:on={section === 'join'} onclick={() => (section = 'join')}><span class="set-nav-icon">↗</span><span>加群频道</span></button>
      <div class="set-nav-label">保护</div>
      <button class="set-nav-item" class:on={section === 'whitelist'} onclick={() => { section = 'whitelist'; onLoadWhitelist(); }}><span class="set-nav-icon">✓</span><span>白名单</span></button>
      <div class="set-nav-spacer"></div>
      <div class="set-nav-label">帮助</div>
      <button class="set-nav-item" class:on={section === 'about'} onclick={() => (section = 'about')}><span class="set-nav-icon">i</span><span>关于</span></button>
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
        <div class="set-sec-title">通用</div>
        <div class="set-group">
          <div class="set-row">
            <span class="set-label">打包文件命名格式</span>
            <input class="set-input" bind:value={settings.pack_naming} placeholder="{name}_账号包" />
          </div>
          <div class="set-row">
            <span class="set-label">默认压缩密码（AES-256）</span>
            <input class="set-input" type="password" autocomplete="new-password" bind:value={settings.pack_password} placeholder="留空则不启用加密" />
          </div>
          <div class="set-row">
            <span class="set-label">日志等级</span>
            <select class="set-select" bind:value={settings.log_level}>
              <option value="info">常规（info）</option>
              <option value="debug">调试（debug，包含蓝牙诊断等原始日志）</option>
            </select>
          </div>
          <div class="set-row set-row-col">
            <span class="set-label">文件夹重命名快捷项（勾选后显示在弹窗中）</span>
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
            <span class="set-label">快捷项自定义前缀</span>
            <input class="set-input" bind:value={settings.rename_prefix} placeholder="例如 tg_" title="选择快捷项时自动添加到文件夹名前" />
          </div>
        </div>
      {:else if section === 'appearance'}
        <div class="set-sec-title">外观</div>
        <div class="set-group">
          <div class="mode-seg">
            <button class="mode-item" class:on={themeMode === 'light'} title="浅色" onclick={() => setThemeMode('light')}>
              {#if themeMode === 'light'}✓{/if} ☀️ 浅色
            </button>
            <button class="mode-item" class:on={themeMode === 'dark'} title="深色" onclick={() => setThemeMode('dark')}>
              {#if themeMode === 'dark'}✓{/if} 🌙 深色
            </button>
          </div>
        </div>
        <div class="set-group-title">色彩主题</div>
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
            <label class="swatch custom" class:on={!isPreset()} title="自定义颜色">
              🖌️
              <input type="color" bind:value={settings.theme_seed} onchange={() => applyTheme()} />
            </label>
          </div>
        </div>
        <div class="set-group-title">详细调整</div>
        <div class="set-group">
          <div class="set-row">
            <span class="set-label">背景浅色</span>
            <input class="set-color" type="color" bind:value={settings.theme_bg} onchange={() => applyTheme()} />
          </div>
          <div class="set-row">
            <span class="set-label">背景深色（卡片）</span>
            <input class="set-color" type="color" bind:value={settings.theme_dark} onchange={() => applyTheme()} />
          </div>
          <div class="set-row">
            <span class="set-label">顶栏颜色</span>
            <input class="set-color" type="color" bind:value={settings.theme_topbar} onchange={() => applyTheme()} />
          </div>
        </div>
        <div class="set-group-title">功能区排序</div>
        <div class="set-group">
          {#each cardOrder as c, i (c)}
            <div class="set-row">
              <span class="set-label">{c}</span>
              <span class="order-btns">
                <button class="order-btn" disabled={i === 0} title="上移" onclick={() => moveCard(i, -1)}>↑</button>
                <button class="order-btn" disabled={i === cardOrder.length - 1} title="下移" onclick={() => moveCard(i, 1)}>↓</button>
              </span>
            </div>
          {/each}
        </div>
      {:else if section === 'proxy'}
        <div class="set-sec-title">代理</div>
        <div class="set-group">
          <div class="set-row">
            <span class="set-label">代理模式</span>
            <select class="set-select" bind:value={settings.proxy_mode}>
              <option value="none">不使用代理</option>
              <option value="system">使用系统代理</option>
              <option value="manual">手动设置</option>
            </select>
          </div>
          {#if settings.proxy_mode === 'manual'}
            <div class="set-row">
              <span class="set-label">代理类型</span>
              <select class="set-select" bind:value={settings.proxy_scheme}>
                <option value="socks5">SOCKS5</option>
                <option value="socks4">SOCKS4</option>
                <option value="http">HTTP</option>
              </select>
            </div>
            <div class="set-row">
              <span class="set-label">IP 地址</span>
              <input class="set-input" bind:value={settings.proxy_host} placeholder="127.0.0.1" />
            </div>
            <div class="set-row">
              <span class="set-label">端口</span>
              <input class="set-input" bind:value={settings.proxy_port} placeholder="7890" />
            </div>
          {/if}
        </div>
      {:else if section === 'join'}
        <section class="settings-card join-email-card">
          <div class="settings-card-head">
            <div class="settings-card-icon">@</div>
            <div>
              <h2>预选邮箱</h2>
              <p>登录时可快速填入，避免重复输入。</p>
            </div>
            <span class="settings-card-count">{emailPresets.length} 个</span>
          </div>
          <div class="settings-card-body">
            {#each emailPresets as p, i}
              <div class="join-edit-row email-row">
                <span class="row-index">{String(i + 1).padStart(2, '0')}</span>
                <input class="set-input join-link" bind:value={emailPresets[i]} placeholder="输入邮箱地址" />
                <button class="order-btn row-delete" title="删除此条" aria-label="删除此条" onclick={() => emailPresets.splice(i, 1)}>×</button>
              </div>
            {/each}
            {#if !emailPresets.length}
              <div class="settings-empty">
                <div class="settings-empty-icon">@</div>
                <strong>暂无预选邮箱</strong>
                <span>添加后可在登录邮箱时快速填入。</span>
              </div>
            {/if}
            <md-outlined-button class="add-setting-btn" onclick={() => emailPresets = [...emailPresets, '']}>＋ 添加邮箱</md-outlined-button>
          </div>
        </section>
        <section class="settings-card join-link-card">
          <div class="settings-card-head">
            <div class="settings-card-icon">↗</div>
            <div>
              <h2>加群频道</h2>
              <p>管理常用群组与频道链接，登录后可快速加入。</p>
            </div>
          </div>
          <div class="settings-card-action">
            <span>前往完整的加群频道管理页</span>
            <md-outlined-button onclick={onOpenJoinManager}>打开管理页面 <span aria-hidden="true">→</span></md-outlined-button>
          </div>
        </section>
      {:else if section === 'whitelist'}
        <div class="set-sec-title">白名单</div>
        <p class="set-hint">白名单中的用户与群组不会被删除任务处理。</p>
        <div class="set-group-title">用户白名单</div>
        <div class="set-group">
          <div class="join-edit-row">
            <input class="set-input join-link" placeholder="用户 ID" bind:value={wlUserInput} />
            <md-outlined-button onclick={doAddUser}>添加</md-outlined-button>
          </div>
          <ul class="sec-list">
            {#each wlUsers as u}
              <li class="sec-item"><span>{u}</span><button class="danger" onclick={() => doRemoveUser(u)}>移除</button></li>
            {/each}
          </ul>
        </div>
        <div class="set-group-title">群组/频道白名单</div>
        <div class="set-group">
          <div class="join-edit-row">
            <input class="set-input join-link" placeholder="群组 ID" bind:value={wlGroupInput} />
            <md-outlined-button onclick={doAddGroup}>添加</md-outlined-button>
          </div>
          <ul class="sec-list">
            {#each wlGroups as g}
              <li class="sec-item"><span>{g}</span><button class="danger" onclick={() => doRemoveGroup(g)}>移除</button></li>
            {/each}
          </ul>
        </div>
      {:else if section === 'about'}
        <div class="set-sec-title">关于</div>
        <div class="about-list">
          <div class="about-row"><span class="set-label">程序名</span><span>TG小号工具箱（Web版）</span></div>
          <div class="about-row"><span class="set-label">版本</span><span class="about-ver">v{appVersion || '…'}</span></div>
          <div class="about-row"><span class="set-label">仓库</span><span>github.com/Gutouoff/TG-tools</span></div>
        </div>
      {:else}
        <div class="set-sec-title">通用</div>
      {/if}
      </div>
      <div class="set-footer">
        <md-filled-button onclick={onSave}>保存设置</md-filled-button>
      </div>
    </main>
    <button class="back set-close" title="关闭" onclick={onClose}>✕</button>
  </div>
</div>
