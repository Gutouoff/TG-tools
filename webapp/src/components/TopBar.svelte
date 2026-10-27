<script lang="ts">
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
  <span class="title">TG小号工具箱</span>
  <span class="conn" class:on={connected && !connectingLabel}>{connectingLabel ? `● ${connectingLabel}` : connected ? '● 已连接' : '● 未连接'}</span>
  <button class="topbtn" onclick={onAddAccount}>新建账号</button>
  <button class="topbtn" onclick={onReconnect}>重新连接</button>
  <button class="topbtn" onclick={onLaunchClient}
    oncontextmenu={(e) => { e.preventDefault(); onOpenFolder(); }}
    title="启动当前账号的 Telegram 客户端；右键账号卡片可打开文件夹">启动客户端</button>
  <button class="topbtn" onclick={onDisconnect}>断开连接</button>
  <button class="topbtn" onclick={onPack}>打包</button>
  <button class="topbtn iconbtn" onclick={onToggleTheme} title={themeMode === 'dark' ? '切换到浅色' : '切换到深色'}>
    {themeMode === 'dark' ? '☀️' : '🌙'}
  </button>
  <button class="topbtn" onclick={onSettings}>设置</button>
</header>
