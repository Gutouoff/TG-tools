<script lang="ts">
  import { t } from '../texts';

  let {
    connected,
    connectingLabel,
    themeMode,
    onAddAccount,
    onReconnect,
    onLaunchClient,
    onOpenFolder,
    onDisconnect,
    onPack,
    onToggleTheme,
    onSettings,
  }: {
    connected: boolean;
    connectingLabel: string;
    themeMode: string;
    onAddAccount: () => void;
    onReconnect: () => void;
    onLaunchClient: () => void;
    onOpenFolder: () => void;
    onDisconnect: () => void;
    onPack: () => void;
    onToggleTheme: () => void;
    onSettings: () => void;
  } = $props();
</script>

<header class="topbar">
  <span class="title">{t('app.title')}</span>
  <span class="conn" class:on={connected && !connectingLabel}>{connectingLabel ? `● ${connectingLabel}` : connected ? t('topbar.connected') : t('topbar.disconnected')}</span>
  <button class="topbtn" onclick={onAddAccount}>{t('topbar.newAccount')}</button>
  <button class="topbtn" onclick={onReconnect}>{t('topbar.reconnect')}</button>
  <button class="topbtn" onclick={onLaunchClient}
    oncontextmenu={(e) => { e.preventDefault(); onOpenFolder(); }}
    title={t('topbar.launchClientHint')}>{t('topbar.launchClient')}</button>
  <button class="topbtn" onclick={onDisconnect}>{t('topbar.disconnect')}</button>
  <button class="topbtn" onclick={onPack}>{t('topbar.pack')}</button>
  <button class="topbtn iconbtn" onclick={onToggleTheme} title={themeMode === 'dark' ? t('topbar.themeToLight') : t('topbar.themeToDark')}>
    {themeMode === 'dark' ? '☀️' : '🌙'}
  </button>
  <button class="topbtn" onclick={onSettings}>{t('topbar.settings')}</button>
</header>
