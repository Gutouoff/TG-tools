<script lang="ts">
  let {
    current,
    isOnline,
    chatUnread,
    dialogs,
    dialogsLoading,
    onRefreshDialogs,
    onBack,
    recvOn,
    recvRules,
    onToggleRecv,
    onRecvRuleChange,
    startChatName = $bindable(''),
    startChatTarget,
    startingChat,
    onStartChat,
    avatarColor,
    onOpenDialog,
    curDialog = $bindable(null),
    historyHasMore,
    historyLoading,
    historyError,
    historyMsgs,
    onLoadHistory,
    chatDraft = $bindable(''),
    sending,
    onSendMsg,
  }: {
    current: any | null;
    isOnline: boolean;
    chatUnread: number;
    dialogs: any[];
    dialogsLoading: boolean;
    onRefreshDialogs: () => void;
    onBack: () => void;
    recvOn: boolean;
    recvRules: Record<string, boolean>;
    onToggleRecv: () => void;
    onRecvRuleChange: (key: string) => void;
    startChatName: string;
    startChatTarget: { kind: string; value: string; label: string };
    startingChat: boolean;
    onStartChat: () => void;
    avatarColor: (name: string) => string;
    onOpenDialog: (d: any) => void;
    curDialog: any | null;
    historyHasMore: boolean;
    historyLoading: boolean;
    historyError: string;
    historyMsgs: any[];
    onLoadHistory: (initial: boolean) => void;
    chatDraft: string;
    sending: boolean;
    onSendMsg: () => void;
  } = $props();
</script>

{#if !curDialog}
  <div class="sec-head">
    <h3>会话{#if chatUnread} <span class="badge">{chatUnread > 99 ? '99+' : chatUnread}</span>{/if}</h3>
    <span class="head-btns">
      <button class="back" onclick={onBack}>日志</button>
      <button class="back refresh-btn" disabled={dialogsLoading} aria-busy={dialogsLoading} aria-label="刷新会话列表" onclick={onRefreshDialogs}>{dialogsLoading ? '加载中…' : '⟳ 刷新'}</button>
    </span>
  </div>
  <div class="chat-switch-row">
    <span class="chat-switch-label">
      <span class="status-dot" class:on={recvOn}></span>
      <span class="chat-switch-text">接收新消息</span>
      <em class="chat-state">{recvOn ? '监听中' : '已停止'}</em>
    </span>
    <button
      class="toggle"
      class:on={recvOn}
      role="switch"
      aria-label="接收新消息"
      aria-checked={recvOn}
      disabled={!isOnline}
      title={!isOnline ? '请先连接账号' : recvOn ? '停止接收' : '开始接收'}
      onclick={onToggleRecv}
    >
      <span class="toggle-thumb"></span>
    </button>
  </div>
  <div class="recv-rules-label">自动接收排除项</div>
  <div class="recv-rules">
    <button class="rule-chip" class:on={recvRules.exclude_channels} aria-pressed={recvRules.exclude_channels} disabled={!isOnline} onclick={() => onRecvRuleChange('exclude_channels')}>{recvRules.exclude_channels ? '✓ ' : ''}排除频道</button>
    <button class="rule-chip" class:on={recvRules.exclude_groups} aria-pressed={recvRules.exclude_groups} disabled={!isOnline} onclick={() => onRecvRuleChange('exclude_groups')}>{recvRules.exclude_groups ? '✓ ' : ''}排除群组</button>
    <button class="rule-chip" class:on={recvRules.exclude_bots} aria-pressed={recvRules.exclude_bots} disabled={!isOnline} onclick={() => onRecvRuleChange('exclude_bots')}>{recvRules.exclude_bots ? '✓ ' : ''}排除机器人</button>
  </div>
  <div class="start-chat-row">
    <input
      class="chat-input"
      placeholder="@用户名 或 数字 ID"
      bind:value={startChatName}
      disabled={!isOnline}
      onkeydown={(e) => { if (e.key === 'Enter') onStartChat(); }}
    />
    <button class="send-btn" disabled={!startChatTarget.value || startingChat || !isOnline} onclick={onStartChat}>
      {startingChat ? '查找中…' : '聊天'}
    </button>
  </div>
  {#if startChatTarget.label}
    <div class="start-chat-hint" aria-live="polite">
      已识别
      <span class="kind-badge">{startChatTarget.kind === 'id' ? 'ID' : '用户名'}</span>
      <span class="hint-value">{startChatTarget.label}</span>
    </div>
  {/if}
  {#if !current}
    <p class="empty">请先选择账号</p>
  {:else if !isOnline}
    <p class="empty">请先连接账号再查看会话</p>
  {:else if !dialogs.length}
    <p class="empty">{dialogsLoading ? '正在加载会话…' : '暂无会话，请点击右上角「刷新」获取'}</p>
  {/if}
  <ul class="dlg-list">
    {#each dialogs as d (d.id)}
      <li
        class="dlg"
        role="button"
        tabindex="0"
        aria-label={`打开会话 ${d.name}`}
        onclick={() => onOpenDialog(d)}
        onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpenDialog(d); } }}
      >
        <span class="dlg-ava" style="background:{avatarColor(d.name)}">{(d.name || '?')[0]}</span>
        <div class="dlg-body">
          <div class="dlg-row1">
            <span class="dlg-name">{d.name}</span>
            <span class="dlg-time">{d.last_date}</span>
          </div>
          <div class="dlg-row2">
            <span class="dlg-last">{d.last_text || ' '}</span>
            {#if d.unread}<span class="badge">{d.unread > 99 ? '99+' : d.unread}</span>{/if}
          </div>
        </div>
      </li>
    {/each}
  </ul>
{:else}
  <div class="sec-head">
    <h3>{curDialog.name}</h3>
    <span class="head-btns">
      <button class="back" onclick={onBack}>日志</button>
      <button class="back" onclick={() => (curDialog = null)}>会话列表</button>
    </span>
  </div>
  {#if historyHasMore}
    <button class="load-older" disabled={historyLoading} onclick={() => onLoadHistory(false)}>
      {historyLoading ? '加载中…' : '加载更早消息'}
    </button>
  {/if}
  <ul class="chat-history">
    {#each historyMsgs as m (m.id)}
      <li class="bbl-row" class:out={m.out}>
        <div class="bbl">
          {#if !m.out && curDialog.type === 'group' && m.sender}<span class="bbl-sender">{m.sender}</span>{/if}
          <div class="bbl-text">{m.text || '[媒体消息]'}<span class="bbl-time">{m.date}{m.out ? ' ✓✓' : ''}</span></div>
        </div>
      </li>
    {/each}
    {#if historyError}
      <li class="empty chat-empty-state" style="color: var(--md-sys-color-error)">
        历史消息加载失败：{historyError}
        <button class="back" onclick={() => onLoadHistory(true)}>[重试]</button>
      </li>
    {:else if !historyMsgs.length}
      <li class="empty chat-empty-state">{historyLoading ? '正在加载…' : '暂无消息'}</li>
    {/if}
  </ul>
  <div class="chat-input-row">
    <input
      class="chat-input"
      placeholder="输入消息（仅支持文本）"
      bind:value={chatDraft}
      disabled={!isOnline}
      onkeydown={(e) => { if (e.key === 'Enter') onSendMsg(); }}
    />
    <button class="send-btn" disabled={sending || !chatDraft.trim()} onclick={onSendMsg}>
      {sending ? '发送中…' : '发送'}
    </button>
  </div>
{/if}
